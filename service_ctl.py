#!/usr/bin/env python3
"""
Bingo 服务管理工具 (交互式)
用法: python3 service_ctl.py
"""

import subprocess
import sys

SERVICES = ["bingo", "nginx"]


def run(cmd):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def get_status_icon(svc):
    _, out, _ = run(f"systemctl is-active {svc}")
    return ("🟢", out) if out == "active" else ("🔴", out)


def show_status():
    print(f"\n{'─'*50}")
    print("📋 当前服务状态:")
    print(f"{'─'*50}")
    for svc in SERVICES:
        icon, state = get_status_icon(svc)
        print(f"  {icon} {svc}: {state}")
    print()


def do_action(action, label):
    print(f"\n⏳ 正在{label}服务...\n")
    for svc in SERVICES:
        code, _, err = run(f"systemctl {action} {svc}")
        if code == 0:
            print(f"  ✅ {svc} {label}成功")
        else:
            print(f"  ❌ {svc} {label}失败: {err}")
    show_status()


def main():
    while True:
        print("╔══════════════════════════════════════════╗")
        print("║       Bingo 服务管理工具                 ║")
        print("╠══════════════════════════════════════════╣")
        print("║                                          ║")
        print("║   1. 启动服务                            ║")
        print("║   2. 停止服务                            ║")
        print("║   3. 重启服务                            ║")
        print("║   4. 查看状态                            ║")
        print("║   0. 退出                                ║")
        print("║                                          ║")
        print("╚══════════════════════════════════════════╝")

        choice = input("\n请选择操作 [0-4]: ").strip()

        if choice == "1":
            do_action("start", "启动")
        elif choice == "2":
            do_action("stop", "停止")
        elif choice == "3":
            do_action("restart", "重启")
        elif choice == "4":
            show_status()
        elif choice == "0":
            print("\n👋 再见！\n")
            sys.exit(0)
        else:
            print("\n⚠️ 无效选项，请重新输入\n")


if __name__ == "__main__":
    main()
