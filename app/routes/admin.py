from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models.user import User
from app.models.team import Team
from app.models.user_team import UserTeam
from app import db
from werkzeug.security import generate_password_hash
from app.models.problem import Problem
from app.models.bingo_config import BingoConfig
from app.models.submission import Submission
from app.models.problem import Problem
from app.models.review import Review
from app.models.review import Review
from sqlalchemy import or_
from app.utils.bingo import calc_bingo_for_team, get_completed_problem_ids_by_team
from app.models.user_team import UserTeam
from app.models.spy_score import SpyScore



admin_bp = Blueprint("admin_bp", __name__)

def super_admin_required(func):
    from functools import wraps
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_super_admin:
            flash("仅超级管理员可访问")
            return redirect(url_for("auth_bp.login"))
        return func(*args, **kwargs)
    return wrapper

# ✅ 用户管理主界面
from flask import request
from sqlalchemy import or_

@admin_bp.route("/users")
@login_required
@super_admin_required
def user_list():
    # 搜索关键词
    search_query = request.args.get("q", "").strip()
    page = int(request.args.get("page", 1))
    per_page = 10

    # 用户查询：是否有关键词搜索
    base_query = User.query
    if search_query:
        base_query = base_query.filter(User.username.ilike(f"%{search_query}%"))

    # 分页处理
    paginated_users = base_query.order_by(User.id).paginate(page=page, per_page=per_page, error_out=False)
    users = paginated_users.items

    # 团队信息
    teams = Team.query.order_by(Team.id).all()
    user_team_links = UserTeam.query.all()

    # 用户 -> 团队映射
    user_team_map = {ut.user_id: ut.team_id for ut in user_team_links}
    spy_ids = {ut.user_id for ut in user_team_links if ut.is_spy}

    # 团队成员列表
    team_members = {t.id: [] for t in teams}
    for ut in user_team_links:
        user = User.query.get(ut.user_id)
        team_members[ut.team_id].append(user)

    return render_template("admin/users.html",
                           users=users,
                           pagination=paginated_users,
                           teams=teams,
                           user_team_map=user_team_map,
                           spy_ids=spy_ids,
                           team_members=team_members,
                           team_count=len(teams),
                           search_query=search_query)



@admin_bp.route("/users/set_team_count", methods=["POST"])
@login_required
@super_admin_required
def set_team_count():
    new_count = int(request.form["team_count"])

    # ✅ 不动默认团队（id=0），处理所有正常团队（id>0）
    existing_normal_teams = Team.query.filter(Team.id != 0).order_by(Team.id).all()

    # ✅ 删除所有旧团队（id > 0）及其用户关联（重建编号从 1 开始）
    delete_ids = [t.id for t in existing_normal_teams]
    UserTeam.query.filter(UserTeam.team_id.in_(delete_ids)).delete(synchronize_session=False)
    for t in existing_normal_teams:
        db.session.delete(t)

    # ✅ 创建新团队（编号从 1 到 new_count）
    for i in range(1, new_count + 1):
        db.session.add(Team(id=i, name=f"团队 {i}"))

    db.session.commit()
    flash("✅ 团队数量已更新")
    return redirect(url_for("admin_bp.user_list"))



from app.models.user_team import UserTeam  # 确保你有这个导入

@admin_bp.route("/users/delete/<int:user_id>")
@login_required
@super_admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.is_super_admin:
        flash("❌ 无法删除超级管理员")
        return redirect(url_for("admin_bp.user_list"))

    # ✅ 删除前先移除 UserTeam 中的关联关系
    UserTeam.query.filter_by(user_id=user.id).delete()

    # ✅ 删除用户本身
    db.session.delete(user)
    db.session.commit()

    flash(f"✅ 用户 {user.username} 已删除")
    return redirect(url_for("admin_bp.user_list"))


@admin_bp.route("/users/set_spy/<int:user_id>")
@login_required
@super_admin_required
def set_spy(user_id):
    from app.models.user_team import UserTeam
    user = User.query.get_or_404(user_id)

    if user.is_admin:
        flash("❌ 管理员不能设置为间谍")
        return redirect(url_for("admin_bp.user_list"))

    user_team = UserTeam.query.filter_by(user_id=user.id).first()

    # ✅ 若没有团队记录，自动加入一个默认团队（第一个团队）
    if not user_team:
        default_team = Team.query.order_by(Team.id).first()
        if not default_team:
            flash("⚠️ 尚未创建任何团队")
            return redirect(url_for("admin_bp.user_list"))
        user_team = UserTeam(user_id=user.id, team_id=default_team.id, is_spy=True)
        db.session.add(user_team)
        db.session.commit()
        flash(f"✅ 用户 {user.username} 已加入 {default_team.name} 并设为间谍")
        return redirect(url_for("admin_bp.user_list"))

    # ✅ 否则进行“切换间谍状态”
    user_team.is_spy = not user_team.is_spy
    db.session.commit()

    status = "设为间谍" if user_team.is_spy else "取消间谍"
    flash(f"✅ 用户 {user.username} 已{status}")
    return redirect(url_for("admin_bp.user_list"))


@admin_bp.route("/users/assign_team", methods=["POST"])
@login_required
@super_admin_required
def assign_team():
    user_id = int(request.form["user_id"])
    team_id_str = request.form.get("team_id", "").strip()

    try:
        team_id = int(team_id_str)
    except ValueError:
        team_id = 0  # 默认未分配团队 ID

    # 删除原有团队关系
    UserTeam.query.filter_by(user_id=user_id).delete()

    # 新增关系（非间谍）
    new_relation = UserTeam(user_id=user_id, team_id=team_id, is_spy=False)
    db.session.add(new_relation)
    db.session.commit()
    flash("✅ 用户团队更新成功")
    return redirect(url_for("admin_bp.user_list"))




# ✅ 导入用户 CSV（格式：username,password,is_admin）
@admin_bp.route("/import_users", methods=["POST"])
@login_required
@super_admin_required
def import_users():
    file = request.files.get("file")
    if not file:
        flash("❌ 未上传文件")
        return redirect(url_for("admin_bp.user_list"))

    success_count = 0
    lines = file.read().decode("utf-8").splitlines()

    for line in lines:
        parts = line.strip().split(",")
        if len(parts) != 5:
            continue  # 格式错误，跳过

        username, pwd, is_admin, is_spy, team_id_str = parts
        username = username.strip()

        if User.query.filter_by(username=username).first():
            continue  # 用户名已存在，跳过

        # 创建用户
        new_user = User(
            username=username,
            password_hash=generate_password_hash(pwd.strip()),
            is_admin=(is_admin.strip() == "1")
        )
        db.session.add(new_user)
        db.session.flush()  # 获取 new_user.id

        # 解析团队 ID
        try:
            team_id = int(team_id_str.strip())
        except ValueError:
            team_id = 0  # 默认无团队

        # ✅ 确保 team_id 所在团队存在
        if team_id > 0 and not Team.query.get(team_id):
            db.session.add(Team(id=team_id, name=f"团队 {team_id}"))

        # ✅ 创建 UserTeam 关系（不管是否启用 is_spy 字段）
        user_team = UserTeam(
            user_id=new_user.id,
            team_id=team_id,
            is_spy=(is_spy.strip() == "1") if is_spy.strip() in ["0", "1"] else False
        )
        db.session.add(user_team)

        success_count += 1

    db.session.commit()
    flash(f"✅ 成功导入 {success_count} 位用户")
    return redirect(url_for("admin_bp.user_list"))

# ✅ 设置为管理员
@admin_bp.route("/set_admin/<int:user_id>")
@login_required
@super_admin_required
def set_admin(user_id):
    user = User.query.get_or_404(user_id)
    user.is_admin = True
    db.session.commit()
    flash(f"{user.username} 已升级为管理员")
    return redirect(url_for("admin_bp.user_list"))

@admin_bp.route("/dashboard")
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        return redirect("/player/dashboard")

    bingo_config = BingoConfig.query.get(1)
    if not bingo_config:
        bingo_config = BingoConfig(matrix_size=5)
        db.session.add(bingo_config)
        db.session.commit()

    total = Problem.query.count()
    return render_template(
        "admin/dashboard.html",
        user=current_user,
        bingo_config=bingo_config,  # ⚠️ 避免与 app.config 冲突
        problem_count=total
    )


@admin_bp.route("/users/new", methods=["GET", "POST"])
@login_required
@super_admin_required
def create_user():
    from app.models.user_team import UserTeam
    from app.models.team import Team

    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        is_admin = request.form.get("is_admin") == "on"
        is_spy = request.form.get("is_spy") == "on"
        team_id = request.form.get("team_id")

        if User.query.filter_by(username=username).first():
            flash("用户名已存在")
            return redirect(url_for("admin_bp.create_user"))

        new_user = User(
            username=username,
            password_hash=generate_password_hash(password),
            is_admin=is_admin
        )
        db.session.add(new_user)
        db.session.commit()

        # 如果不是管理员，允许加入团队
        if not is_admin:
            try:
                team_id = int(team_id) if team_id else 0
            except ValueError:
                team_id = 0  # 默认未分配

            db.session.add(UserTeam(
                user_id=new_user.id,
                team_id=team_id,
                is_spy=is_spy
            ))
            db.session.commit()

        flash("✅ 用户创建成功")
        return redirect(url_for("admin_bp.user_list"))

    teams = Team.query.order_by(Team.id).all()
    return render_template("admin/create_user.html", teams=teams)


@admin_bp.route("/users/<int:user_id>/reset_password", methods=["GET", "POST"])
@login_required
@super_admin_required
def reset_password(user_id):
    user = User.query.get_or_404(user_id)
    if request.method == "POST":
        new_pwd = request.form["password"]
        user.password_hash = generate_password_hash(new_pwd)
        db.session.commit()
        flash("✅ 密码已更新")
        return redirect(url_for("admin_bp.user_list"))
    return render_template("admin/reset_password.html", user=user)

@admin_bp.route("/unset_admin/<int:user_id>")
@login_required
@super_admin_required
def unset_admin(user_id):
    user = User.query.get_or_404(user_id)
    if user.is_super_admin:
        flash("❌ 无法撤销超级管理员权限")
    else:
        user.is_admin = False
        db.session.commit()
        flash("权限已撤销")
    return redirect(url_for("admin_bp.user_list"))

@admin_bp.route("/problems", methods=["GET", "POST"])
@login_required
def problem_matrix():
    if not current_user.is_admin:
        return redirect("/player/dashboard")

    config = BingoConfig.query.get(1)
    if not config:
        config = BingoConfig(matrix_size=5)
        db.session.add(config)
        db.session.commit()

    if request.method == "POST":
        new_size = int(request.form["matrix_size"])
        if new_size != config.matrix_size:
            # 清空题目再修改大小
            Problem.query.delete()
            db.session.commit()
            config.matrix_size = new_size
            db.session.commit()
            flash("✅ 大小已修改，题库已重置")
        return redirect(url_for("admin_bp.problem_matrix"))

    problems = Problem.query.all()
    problem_dict = {(p.row_index, p.col_index): p for p in problems}
    return render_template("admin/problem_matrix.html", config=config, problem_dict=problem_dict)


@admin_bp.route("/problems/edit/<int:row>/<int:col>", methods=["GET", "POST"])
@login_required
def edit_problem(row, col):
    if not current_user.is_admin:
        return redirect("/player/dashboard")

    config = BingoConfig.query.get(1)
    problem = Problem.query.filter_by(row_index=row, col_index=col).first()

    if request.method == "POST":
        normal_q = request.form.get("normal_question", "")
        spy_q = request.form.get("spy_question", "")

        if not problem:
            problem = Problem(row_index=row, col_index=col)
            db.session.add(problem)

        problem.normal_question = normal_q.strip()
        # ✅ 如果开启间谍功能，保存间谍题目；否则清空
        problem.spy_question = spy_q.strip() if config.spy_enabled else None
        problem.is_published = True  # ✅ 默认保存即发布

        db.session.commit()
        flash(f"✅ 题目 ({row},{col}) 已成功保存并发布")
        return redirect(url_for("admin_bp.problem_matrix"))

    return render_template("admin/edit_problem.html",
                           problem=problem,
                           row=row,
                           col=col,
                           config=config)


@admin_bp.route("/toggle_spy", methods=["POST"])
@login_required
def toggle_spy():
    if not current_user.is_admin:
        return redirect("/player/dashboard")

    config = BingoConfig.query.get(1)
    if not config:
        config = BingoConfig(matrix_size=5)  # 初始化默认配置
        db.session.add(config)

    config.spy_enabled = "spy_enabled" in request.form
    db.session.commit()
    flash("✅ 间谍功能设置已更新")
    return redirect(url_for("admin_bp.admin_dashboard"))


@admin_bp.route("/review")
@login_required
def review_list():
    if not current_user.is_admin:
        return redirect("/player/dashboard")

    # 所有团队映射（用于显示团队名称）
    teams = Team.query.all()
    team_map = {team.id: team for team in teams}

    # 所有 pending，按题目+团队保留最新提交
    all_pending = Submission.query.filter_by(status="pending").order_by(Submission.submitted_at.desc()).all()
    seen_keys = set()
    pending = []

    for sub in all_pending:
        user_team = UserTeam.query.filter_by(user_id=sub.user_id).first()
        team_id = user_team.team_id if user_team else 0
        key = (sub.problem_id, team_id)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        prob = Problem.query.get(sub.problem_id)
        user = User.query.get(sub.user_id)
        pending.append((sub, prob, user, team_id))

    # 所有有 Review 的提交记录（无论现在状态如何）
    all_reviews = Review.query.order_by(Review.reviewed_at.desc()).all()
    reviewed = []
    final_keys = set()

    # 收集“最终归档的”提交 (用于标记 is_final)
    archived_subs = Submission.query.filter_by(status="archived").all()
    for sub in archived_subs:
        user_team = UserTeam.query.filter_by(user_id=sub.user_id).first()
        team_id = user_team.team_id if user_team else 0
        key = (sub.problem_id, team_id)
        final_keys.add((sub.id, key))

    # 汇总所有已审核记录
    for review in all_reviews:
        sub = Submission.query.get(review.submission_id)
        if not sub:
            continue
        prob = Problem.query.get(sub.problem_id)
        user = User.query.get(sub.user_id)
        admin = User.query.get(review.admin_id)
        user_team = UserTeam.query.filter_by(user_id=sub.user_id).first()
        team_id = user_team.team_id if user_team else 0
        key = (sub.problem_id, team_id)
        is_final = (sub.id, key) in final_keys
        reviewed.append((sub, prob, user, review, admin, is_final, team_id))

    return render_template("admin/review_list.html",
                           pending=pending,
                           reviewed=reviewed,
                           team_map=team_map)




@admin_bp.route("/history/<int:user_id>/<int:problem_id>")
@login_required
def view_submission_history(user_id, problem_id):
    if not current_user.is_admin:
        return redirect("/player/dashboard")

    subs = Submission.query.filter_by(user_id=user_id, problem_id=problem_id).order_by(Submission.submitted_at.asc()).all()
    user = User.query.get(user_id)
    problem = Problem.query.get(problem_id)

    # 获取该用户所属团队
    user_team = UserTeam.query.filter_by(user_id=user.id).first()
    team_id = user_team.team_id if user_team else 0

    # 获取该团队的最终归档记录
    archived = Submission.query.filter_by(problem_id=problem_id, status="archived").all()
    final_sub_ids = {s.id for s in archived if UserTeam.query.filter_by(user_id=s.user_id, team_id=team_id).first()}

    review_map = {}
    for sub in subs:
        review = Review.query.filter_by(submission_id=sub.id).order_by(Review.reviewed_at.desc()).first()
        admin = User.query.get(review.admin_id) if review else None
        is_final = sub.id in final_sub_ids
        review_map[sub.id] = (review, admin, is_final)

    return render_template("admin/submission_history.html",
                           user=user,
                           problem=problem,
                           submissions=subs,
                           review_map=review_map)


@admin_bp.route("/review/<int:submission_id>", methods=["GET", "POST"])
@login_required
def review_submission(submission_id):
    if not current_user.is_admin:
        flash("无权访问")
        return redirect("/player/dashboard")

    sub = Submission.query.get_or_404(submission_id)
    prob = Problem.query.get(sub.problem_id)
    user = User.query.get(sub.user_id)
    config = BingoConfig.query.get(1)

    user_team = UserTeam.query.filter_by(user_id=user.id).first()
    team_id = user_team.team_id if user_team else 0
    is_spy = user_team.is_spy if user_team else False

    visible_question = prob.spy_question if (is_spy and config.spy_enabled) else prob.normal_question

    if request.method == "POST":
        action = request.form.get("action", "").strip()
        comment = request.form.get("comment", "").strip()
        spy_attack = request.form.get("spy_attack") == "on"

        if action == "approve":
            sub.status = "archived"
            result = "approved"
        elif action == "reject":
            sub.status = "rejected"
            result = "rejected"
        else:
            flash("❌ 无效操作")
            return redirect(url_for("admin_bp.review_submission", submission_id=sub.id))

        db.session.add(sub)

        # ✅ 添加审核记录
        review = Review(
            submission_id=sub.id,
            admin_id=current_user.id,
            result=result,
            comment=comment,
            is_spy_attack=spy_attack
        )
        db.session.add(review)

        # ✅ 将同题同团队下所有旧 pending 提交，标记为 rejected（被自动覆盖）
        old_subs = Submission.query.join(UserTeam, Submission.user_id == UserTeam.user_id).filter(
            Submission.problem_id == sub.problem_id,
            UserTeam.team_id == team_id,
            Submission.status == "pending",
            Submission.id != sub.id  # 不包括当前审核的
        ).all()

        for old in old_subs:
            old.status = "rejected"
            db.session.add(old)
            db.session.add(Review(
                submission_id=old.id,
                admin_id=current_user.id,
                result="rejected",
                comment="⛔ 被新提交覆盖自动拒绝",
                is_spy_attack=False
            ))

        db.session.commit()
        flash("✅ 审核完成（旧提交已自动标记为无效）")
        return redirect(url_for("admin_bp.review_list"))

    return render_template(
        "admin/review_detail.html",
        submission=sub,
        problem=prob,
        user=user,
        config=config,
        is_spy=is_spy,
        visible_question=visible_question
    )



@admin_bp.route("/teams")
@login_required
def team_panel():
    if not current_user.is_admin:
        return redirect("/player/dashboard")

    teams = Team.query.all()
    user_team_links = UserTeam.query.all()
    user_map = {u.id: u for u in User.query.all()}
    team_members = {team.id: [] for team in teams}
    spies = []

    for ut in user_team_links:
        user = user_map[ut.user_id]
        team_members[ut.team_id].append((user, ut.is_spy))
        if ut.is_spy:
            spies.append((user, ut.team_id))

    # ✅ 提交统计应基于完整的 Review 数据
    team_stats = {team.id: {"total": 0, "passed": 0, "rejected": 0, "bingo": 0} for team in teams}

    # 所有与审核有关的记录
    all_reviews = Review.query.join(Submission, Review.submission_id == Submission.id).all()

    for review in all_reviews:
        submission = Submission.query.get(review.submission_id)
        if not submission:
            continue
        user_team = UserTeam.query.filter_by(user_id=submission.user_id).first()
        if not user_team:
            continue
        team_id = user_team.team_id
        if team_id not in team_stats:
            continue

        team_stats[team_id]["total"] += 1
        if review.result in ["approved", "approve"]:
            team_stats[team_id]["passed"] += 1
        elif review.result in ["rejected", "reject"]:
            team_stats[team_id]["rejected"] += 1

    # ✅ 统计 Bingo（仍使用现有函数）
    for team in teams:
        team_stats[team.id]["bingo"] = calc_bingo_for_team(team.id)

    # ✅ 统计间谍得分
    spy_scores = {user.id: 0 for user, _ in spies}
    spy_teams = {user.id: team_id for user, team_id in spies}

    spy_attacks = Review.query.filter_by(is_spy_attack=True).all()
    for review in spy_attacks:
        sub = Submission.query.get(review.submission_id)
        if not sub:
            continue
        attacked_team = UserTeam.query.filter_by(user_id=sub.user_id).first()
        if not attacked_team:
            continue
        attacked_team_id = attacked_team.team_id
        for spy_user, spy_team_id in spies:
            if spy_team_id == attacked_team_id:
                spy_scores[spy_user.id] += 1

    # ✅ 叠加手动得分
    for user_id in spy_scores:
        manual = SpyScore.query.filter_by(user_id=user_id).first()
        if manual:
            spy_scores[user_id] += manual.score

    return render_template("admin/team_panel.html",
                           teams=teams,
                           team_members=team_members,
                           team_stats=team_stats,
                           spies=spies,
                           spy_scores=spy_scores,
                           user_map=user_map)




@admin_bp.route("/update_spy_scores", methods=["POST"])
@login_required
@super_admin_required
def update_spy_scores():
    user_ids = request.form.getlist("user_ids")
    for uid in user_ids:
        try:
            adj = int(request.form.get(f"adjustments_{uid}", "0"))
            if adj == 0:
                continue
            score = SpyScore.query.filter_by(user_id=uid).first()
            if not score:
                score = SpyScore(user_id=uid, score=0)
                db.session.add(score)
            score.score += adj
        except Exception as e:
            print(f"跳过用户 {uid} 的手动加分（原因: {e}）")
            continue

    db.session.commit()
    flash("✅ 间谍得分已成功更新")
    return redirect(url_for("admin_bp.team_panel"))