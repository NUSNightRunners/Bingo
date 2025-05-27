from flask import Blueprint, render_template, request, redirect, url_for, flash, session, send_file
from flask_login import login_user, logout_user, login_required, current_user
from app.models.user import User
from app import db, login_manager
from werkzeug.security import check_password_hash
import random
import string
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

auth_bp = Blueprint('auth_bp', __name__)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# 验证码图片路由
@auth_bp.route("/captcha")
def captcha():
    code = ''.join(random.choices(string.digits, k=4))
    session["captcha"] = code

    # 生成图像
    width, height = 100, 40
    image = Image.new('RGB', (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()

    for i, char in enumerate(code):
        draw.text((10 + i * 20, 10), char, font=font, fill=(0, 0, 0))

    for _ in range(5):
        x1 = random.randint(0, width)
        y1 = random.randint(0, height)
        x2 = random.randint(0, width)
        y2 = random.randint(0, height)
        draw.line(((x1, y1), (x2, y2)), fill=(120, 120, 120), width=1)

    buffer = BytesIO()
    image.save(buffer, 'PNG')
    buffer.seek(0)
    return send_file(buffer, mimetype='image/png')


@auth_bp.route("/", methods=["GET", "POST"])
def login():
    # ✅ 已登录用户直接跳转 dashboard
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect("/admin/dashboard")
        else:
            return redirect("/player/dashboard")

    # ✅ 尚未登录，处理表单或展示登录页
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        captcha_input = request.form["captcha"].strip()
        captcha_session = session.get("captcha", "")

        if captcha_input != captcha_session:
            flash("验证码错误，请重试")
            return redirect(url_for("auth_bp.login"))

        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            if user.is_admin:
                return redirect("/admin/dashboard")
            else:
                return redirect("/player/dashboard")
        flash("登录失败，请检查用户名或密码")

    return render_template("auth/login.html")

@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    session.clear()  # ✅ 清除 session
    flash("您已成功登出")
    return redirect(url_for("auth_bp.login"))

@auth_bp.route("/help")
def help_page():
    return render_template("public/help.html")

