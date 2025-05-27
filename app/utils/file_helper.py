import os
import uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app import db
from app.models.problem import Problem
from app.models.submission import Submission
from app.models.bingo_config import BingoConfig

player_bp = Blueprint("player_bp", __name__)

# 允许的扩展名
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'webm', 'mov'}

# 上传文件夹配置（基于项目目录）
BASE_DIR = os.path.abspath(os.path.dirname(__file__))  # app/routes/
UPLOAD_FOLDER = os.path.normpath(os.path.join(BASE_DIR, "..", "..", "static", "uploads"))

# 检查是否允许文件
def is_allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# 生成随机文件名
def generate_safe_filename(filename):
    ext = filename.rsplit('.', 1)[-1].lower()
    return f"{uuid.uuid4().hex}.{ext}"
