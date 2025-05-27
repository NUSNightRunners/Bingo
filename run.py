from app import create_app, db
import os
from app.models.team import Team

app = create_app()

# ✅ 此时 app 才被定义，可以访问它的属性
print("🧭 Flask 正在以此为根路径启动：", os.getcwd())
print("🧪 Flask static_folder:", app.static_folder)
print("🧪 static_url_path:", app.static_url_path)

def ensure_unassigned_team():
    # ✅ 必须进入 app context 才能访问数据库
    with app.app_context():
        if not Team.query.get(0):
            db.session.add(Team(id=0, name="未分配团队"))
            db.session.commit()
            print("✅ 已创建默认未分配团队 Team(id=0)")

# ⚠️ 确保这个在 __main__ 前执行
ensure_unassigned_team()

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=8080)


