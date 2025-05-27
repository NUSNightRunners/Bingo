import os
from flask import Flask, current_app
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
from flask_migrate import Migrate
from config import Config

# 初始化扩展
db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()

def create_app():
    app = Flask(
        __name__,
        static_folder=os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "static")),
        static_url_path="/static"
    )
    app.config.from_object(Config)

    # 初始化扩展
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)

    # 注册蓝图
    from app.routes import auth_bp, admin_bp, player_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(player_bp, url_prefix="/player")

    # ✅ 注册全局上下文变量（⚠️ 必须在 app 定义之后）
    @app.context_processor
    def inject_user_role():
        return {
            "is_admin": current_user.is_authenticated and current_user.is_admin,
            "is_super_admin": current_user.is_authenticated and current_user.is_super_admin,
            "current_user": current_user
        }

    return app
