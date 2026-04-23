# Bingo Service 运维手册

> 部署日期：2026-04-23  
> 部署路径：/root/Bingo  
> 域名：http://bingo.nightrunner.org/  
> 技术栈：Flask + Gunicorn + Nginx + SQLite

---

## 1. 系统架构

```
用户 → Nginx (80端口) → Gunicorn (127.0.0.1:8080) → Flask App
                ↓
        静态文件 /root/Bingo/static/ (Nginx直接提供)
```

## 2. 关键路径

| 项目 | 路径 |
|------|------|
| 项目代码 | `/root/Bingo/` |
| Python虚拟环境 | `/root/Bingo/venv/` |
| SQLite数据库 | `/root/Bingo/instance/bingo.db` |
| 静态文件 | `/root/Bingo/static/` |
| Gunicorn systemd服务 | `/etc/systemd/system/bingo.service` |
| Nginx站点配置 | `/etc/nginx/sites-available/bingo` |
| Nginx站点启用链接 | `/etc/nginx/sites-enabled/bingo` |
| 数据库迁移文件 | `/root/Bingo/migrations/` |
| SSL证书 | `/etc/nginx/ssl/bingo.nightrunner.org.pem` |
| SSL私钥 | `/etc/nginx/ssl/bingo.nightrunner.org.key` |
| SSL证书源文件 | `/root/SLL_Keys/` |


## 3. 常用运维命令

### 3.1 服务管理

```bash
# 查看Bingo服务状态
systemctl status bingo

# 启动/停止/重启Bingo服务
systemctl start bingo
systemctl stop bingo
systemctl restart bingo

# 查看Bingo服务日志
journalctl -u bingo -f          # 实时日志
journalctl -u bingo --since today  # 今日日志
journalctl -u bingo -n 100     # 最近100行

# 查看Nginx状态
systemctl status nginx

# 重载Nginx配置（不中断服务）
systemctl reload nginx

# 重启Nginx
systemctl restart nginx

# 测试Nginx配置是否正确
nginx -t
```

### 3.2 代码更新

```bash
# 1. 拉取最新代码
cd /root/Bingo
git pull origin main

# 2. 安装新依赖（如果requirements.txt有变化）
/root/Bingo/venv/bin/pip install -r requirements.txt

# 3. 执行数据库迁移（如果有模型变更）
FLASK_APP=run.py /root/Bingo/venv/bin/flask db migrate -m "描述"
FLASK_APP=run.py /root/Bingo/venv/bin/flask db upgrade

# 4. 重启服务
systemctl restart bingo
```

### 3.3 数据库管理

```bash
# 数据库备份
cp /root/Bingo/instance/bingo.db /root/Bingo/instance/bingo.db.backup.$(date +%Y%m%d_%H%M%S)

# 数据库迁移
cd /root/Bingo
FLASK_APP=run.py /root/Bingo/venv/bin/flask db migrate -m "变更描述"
FLASK_APP=run.py /root/Bingo/venv/bin/flask db upgrade

# 回滚迁移
FLASK_APP=run.py /root/Bingo/venv/bin/flask db downgrade
```

### 3.4 Nginx管理

```bash
# 查看Nginx完整配置
nginx -T

# 查看Nginx错误日志
tail -f /var/log/nginx/error.log

# 查看Nginx访问日志
tail -f /var/log/nginx/access.log

# 验证上传大小限制配置
nginx -T 2>/dev/null | grep client_max_body_size
# 预期输出: client_max_body_size 2g;
```

## 4. 配置说明

### 4.1 Nginx配置 (`/etc/nginx/sites-available/bingo`)

- `client_max_body_size 2g` — 最大上传/下载文件大小2GB
- `proxy_*_timeout 600` — 代理超时时间600秒，适配大文件传输
- `proxy_buffering off` — 关闭代理缓冲，适合大文件传输
- 静态文件由Nginx直接提供，设置30天缓存

### 4.2 Gunicorn配置 (`/etc/systemd/system/bingo.service`)

- 4个worker进程
- 监听 `127.0.0.1:8080`（仅本地可访问）
- 自动重启策略（失败后5秒重启）

### 4.3 Flask配置 (`/root/Bingo/config.py`)

- 数据库：SQLite (`sqlite:///bingo.db`)
- SECRET_KEY：通过环境变量 `SECRET_KEY` 设置，或使用默认值

## 5. 故障排查

### 5.1 网站无法访问

```bash
# 1. 检查Nginx是否运行
systemctl status nginx

# 2. 检查Bingo服务是否运行
systemctl status bingo

# 3. 直接测试Gunicorn
curl http://127.0.0.1:8080

# 4. 直接测试Nginx
curl http://127.0.0.1:80

# 5. 检查端口占用
ss -tlnp | grep -E '80|8080'

# 6. 检查防火墙
ufw status
```

### 5.2 上传文件失败

```bash
# 检查Nginx上传限制
nginx -T 2>/dev/null | grep client_max_body_size

# 检查Nginx错误日志
tail -20 /var/log/nginx/error.log
```

### 5.3 服务崩溃

```bash
# 查看崩溃日志
journalctl -u bingo --since "1 hour ago"

# 手动启动查看错误
cd /root/Bingo
/root/Bingo/venv/bin/gunicorn --workers 1 --bind 127.0.0.1:8080 run:app
```

## 6. SSL证书管理

### 6.1 证书更新

```bash
# 1. 将新证书文件放入 /root/SLL_Keys/
# 2. 复制到Nginx SSL目录
cp /root/SLL_Keys/bingo.nightrunner.org.pem /etc/nginx/ssl/
cp /root/SLL_Keys/bingo.nightrunner.org.key /etc/nginx/ssl/
chmod 600 /etc/nginx/ssl/bingo.nightrunner.org.key

# 3. 测试并重载Nginx
nginx -t && systemctl reload nginx
```

### 6.2 查看证书信息

```bash
# 查看证书过期时间
openssl x509 -in /etc/nginx/ssl/bingo.nightrunner.org.pem -noout -dates

# 查看证书详细信息
openssl x509 -in /etc/nginx/ssl/bingo.nightrunner.org.pem -noout -text
```

## 7. 定期维护建议

| 任务 | 频率 | 命令 |
|------|------|------|
| 数据库备份 | 每日 | `cp /root/Bingo/instance/bingo.db /root/Bingo/instance/bingo.db.backup.$(date +%Y%m%d)` |
| 检查磁盘空间 | 每周 | `df -h` |
| 检查服务状态 | 每日 | `systemctl status bingo nginx` |
| 清理Nginx日志 | 每月 | `logrotate` 自动处理 |
| 系统更新 | 每月 | `apt update && apt upgrade` |
