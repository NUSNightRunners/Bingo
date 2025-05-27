import sys
import os

# 加入 app 根路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from app import create_app, db
from app.models.user import User
from werkzeug.security import generate_password_hash

# 设置数据库路径（仅适用于 SQLite）
DB_PATH = 'bingo.db'

def reset_database():
    # 删除旧数据库文件
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"✅ 已删除旧数据库：{DB_PATH}")
    else:
        print(f"⚠️ 数据库文件不存在：{DB_PATH}")

    # 创建新数据库与表结构
    app = create_app()
    with app.app_context():
        db.create_all()
        print("✅ 数据库表结构已创建")

        # 创建超级管理员 Guoyi（仅一次）
        guoyi = User.query.filter_by(username="Guoyi").first()
        if not guoyi:
            super_admin = User(
                username="Guoyi",
                password_hash=generate_password_hash("Cgy31415926"),  # 你可以换一个密码
                is_admin=True,
                is_super_admin=True
            )
            db.session.add(super_admin)
            db.session.commit()
            print("✅ 超级管理员 Guoyi 已创建")
        else:
            print("⚠️ Guoyi 已存在")

if __name__ == "__main__":
    reset_database()
