import os
import uuid
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app import db
from app.models.problem import Problem
from app.models.submission import Submission
from app.models.user import User
from app.models.bingo_config import BingoConfig
from app.models.review import Review
from sqlalchemy import or_
from app.models.user_team import UserTeam
from app.utils.bingo import get_completed_problem_ids_by_team, calc_bingo_for_team
from app.models.team import Team
from app.models.user_team import UserTeam
from app.models.user import User

player_bp = Blueprint("player_bp", __name__)

# 📂 上传路径定义
UPLOAD_FOLDER_REL = "static/uploads"  # 用于页面显示
UPLOAD_FOLDER_ABS = os.path.join(os.path.abspath(os.getcwd()), UPLOAD_FOLDER_REL)  # 用于文件保存

# ✅ 支持的文件类型
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'webm', 'mov'}

# 🔍 检查扩展名
def is_allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# 🔐 安全重命名
def generate_safe_filename(filename):
    ext = filename.rsplit('.', 1)[-1].lower()
    return f"{uuid.uuid4().hex}.{ext}"

@player_bp.route("/dashboard")
@login_required
def player_dashboard():
    from app.models.user_team import UserTeam
    from app.models.user import User
    from app.models.review import Review

    config = BingoConfig.query.get(1)
    problems = Problem.query.all()
    problem_dict = {(p.row_index, p.col_index): p for p in problems}

    # ✅ 当前用户团队信息
    user_team = UserTeam.query.filter_by(user_id=current_user.id).first()
    team_id = user_team.team_id if user_team else 0

    # ✅ 获取团队所有成员 ID
    teammates = UserTeam.query.filter_by(team_id=team_id).all()
    teammate_ids = [t.user_id for t in teammates] if teammates else []

    # ✅ 团队视角下完成的题目 ID（共享）
    from app.utils.bingo import get_completed_problem_ids_by_team
    completed_ids = get_completed_problem_ids_by_team(team_id)

    # ✅ 映射团队中所有题目的提交状态（用于格子着色）
    submissions = Submission.query.filter(
        Submission.user_id.in_(teammate_ids)
    ).all()
    sub_map = {}
    for s in submissions:
        if s.problem_id not in sub_map or s.submitted_at > sub_map[s.problem_id][1]:
            sub_map[s.problem_id] = (s.status, s.submitted_at)

    # 仅提取状态信息用于模板
    sub_map = {pid: status for pid, (status, _) in sub_map.items()}

    # ✅ 获取队友列表（不含自己）用于展示
    teammate_users = db.session.query(User).filter(
        User.id.in_(teammate_ids),
        User.id != current_user.id
    ).all()

    # ✅ 与 admin 保持一致的团队统计逻辑（基于 Review）
    reviewed_stats = {"total": 0, "passed": 0, "rejected": 0}
    reviews = Review.query.join(Submission, Review.submission_id == Submission.id).filter(
        Submission.user_id.in_(teammate_ids)
    ).all()

    for r in reviews:
        reviewed_stats["total"] += 1
        if r.result in ["approved", "approve"]:
            reviewed_stats["passed"] += 1
        elif r.result in ["rejected", "reject"]:
            reviewed_stats["rejected"] += 1

    team_stats = {
        "passed": reviewed_stats["passed"],
        "rejected": reviewed_stats["rejected"],
        "total": reviewed_stats["total"],
        "bingo": calc_bingo_for_team(team_id)
    }

    # ✅ 全部团队 Bingo 排名
    all_teams = Team.query.order_by(Team.id).all()
    all_bingo_counts = [(t.name, calc_bingo_for_team(t.id)) for t in all_teams]
    all_bingo_counts.sort(key=lambda x: x[1], reverse=True)

    return render_template("player/dashboard.html",
                           config=config,
                           problem_dict=problem_dict,
                           completed_ids=completed_ids,
                           sub_map=sub_map,
                           teammates=teammate_users,
                           team_stats=team_stats,
                           all_bingo_counts=all_bingo_counts)




@player_bp.route("/problem/<int:pid>", methods=["GET", "POST"])
@login_required
def view_problem(pid):
    from app.models.user_team import UserTeam
    from app.models.user import User
    from app.models.review import Review
    from app.models.submission import Submission

    problem = Problem.query.get_or_404(pid)
    config = BingoConfig.query.get(1)

    user_team = UserTeam.query.filter_by(user_id=current_user.id).first()
    team_id = user_team.team_id if user_team else 0
    is_spy = user_team.is_spy if user_team else False

    teammate_ids = [ut.user_id for ut in UserTeam.query.filter_by(team_id=team_id).all()]
    if not teammate_ids:
        teammate_ids = [current_user.id]

    # ✅ 全队该题所有提交（时间倒序）
    team_submissions = Submission.query.filter(
        Submission.user_id.in_(teammate_ids),
        Submission.problem_id == pid
    ).order_by(Submission.submitted_at.desc()).all()

    # ✅ 优先显示归档过的提交
    archived_submission = next((s for s in team_submissions if s.status == "archived"), None)
    submission = archived_submission or (team_submissions[0] if team_submissions else None)

    # ✅ 自己的提交记录（用于修改或创建）
    my_submission = Submission.query.filter_by(user_id=current_user.id, problem_id=pid).first()

    displayed_question = problem.spy_question if (is_spy and config.spy_enabled) else problem.normal_question

    is_team_archived = archived_submission is not None

    if request.method == "POST":
        if is_team_archived:
            flash("⚠️ 该题目已由团队成员完成归档，无法再次提交。")
            return redirect(url_for("player_bp.view_problem", pid=pid))

        description = request.form.get("description", "").strip()
        file = request.files.get("image")
        has_description = bool(description)
        has_file = file and file.filename

        if not has_description and not has_file:
            flash("❌ 请至少填写描述或上传图片/视频")
            return redirect(url_for("player_bp.view_problem", pid=pid))

        if not os.path.exists(UPLOAD_FOLDER_ABS):
            os.makedirs(UPLOAD_FOLDER_ABS)

        image_path = my_submission.image_path if my_submission else ""

        if has_file:
            if not is_allowed_file(file.filename):
                flash("❌ 不支持的文件格式（仅支持图片或视频）")
                return redirect(url_for("player_bp.view_problem", pid=pid))

            safe_name = generate_safe_filename(file.filename)
            save_path = os.path.join(UPLOAD_FOLDER_ABS, safe_name)
            file.save(save_path)
            image_path = os.path.join(UPLOAD_FOLDER_REL, safe_name).replace("\\", "/")

        if not my_submission:
            my_submission = Submission(
                user_id=current_user.id,
                problem_id=pid,
                image_path=image_path,
                description=description,
                status="pending"
            )
            db.session.add(my_submission)
        else:
            if has_file:
                my_submission.image_path = image_path
            if has_description:
                my_submission.description = description
            my_submission.status = "pending"

        db.session.commit()
        flash("✅ 提交成功，等待管理员审核")
        return redirect(url_for("player_bp.player_dashboard"))

    user_map = {u.id: u for u in User.query.filter(User.id.in_(teammate_ids)).all()}
    review_map = {
        sub.id: Review.query.filter_by(submission_id=sub.id)
                            .order_by(Review.reviewed_at.desc()).first()
        for sub in team_submissions
    }

    return render_template("player/problem_detail.html",
                           problem=problem,
                           config=config,
                           submission=submission,
                           all_team_submissions=team_submissions,
                           question=displayed_question,
                           is_spy=is_spy,
                           user_map=user_map,
                           review_map=review_map,
                           is_team_archived=is_team_archived)


@player_bp.route("/messages")
@login_required
def message_center():
    # 查询所有该用户被审核过的记录（Review 为主表）
    reviews = Review.query.join(Submission, Review.submission_id == Submission.id).filter(
        Submission.user_id == current_user.id
    ).order_by(Review.reviewed_at.desc()).all()

    messages = []
    for review in reviews:
        sub = Submission.query.get(review.submission_id)
        prob = Problem.query.get(sub.problem_id)
        admin = User.query.get(review.admin_id) if review.admin_id else None
        messages.append((sub, prob, review, admin))

    return render_template("player/messages.html", messages=messages)


# 在 routes/player.py 中添加：
@player_bp.route("/change_password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        from werkzeug.security import check_password_hash, generate_password_hash
        current_pwd = request.form.get("current_password", "").strip()
        new_pwd = request.form.get("new_password", "").strip()
        confirm_pwd = request.form.get("confirm_password", "").strip()

        if not check_password_hash(current_user.password_hash, current_pwd):
            flash("❌ 当前密码错误")
        elif not new_pwd or new_pwd != confirm_pwd:
            flash("❌ 新密码不一致或为空")
        else:
            current_user.password_hash = generate_password_hash(new_pwd)
            db.session.commit()
            flash("✅ 密码修改成功")
            return redirect(url_for("player_bp.player_dashboard"))

    return render_template("player/change_password.html")

@player_bp.route("/help")
def help_page():
    return render_template("public/help.html")