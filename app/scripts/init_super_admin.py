import sys
import os

# 加入 app 根路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from app import create_app, db
from app.models.user import User
from werkzeug.security import generate_password_hash

app = create_app()

with app.app_context():
    user = User.query.filter_by(username="Guoyi").first()
    if user:
        user.password_hash = generate_password_hash("Cgy31415926")  # 强制修改
        db.session.commit()
        print("🔁 Password for Guoyi has been updated.")
    else:
        guoyi = User(
            username="Guoyi",
            password_hash=generate_password_hash("Cgy31415926"),
            is_admin=True,
            is_super_admin=True
        )
        db.session.add(guoyi)
        db.session.commit()
        print("✅ Super Admin 'Guoyi' created.")
