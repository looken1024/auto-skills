#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""头条发布异常邮件通知（163 SMTP）

用法:
    python3 notify_email.py "异常类型" "错误详情" ["文案首句"]

配置（按优先级）:
    1. 环境变量 SMTP_USER / SMTP_AUTH_CODE / NOTIFY_TO
    2. skills/toutiao-micro-publish/config/smtp.json
        {"user": "18518007500@163.com", "auth_code": "16位授权码", "to": "18518007500@163.com"}
"""
import os, sys, json, smtplib
from email.mime.text import MIMEText
from email.header import Header
from datetime import datetime
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
CONFIG = SKILL_DIR / "config" / "smtp.json"


def load_config():
    cfg = {}
    for k, env in [("user", "SMTP_USER"), ("auth_code", "SMTP_AUTH_CODE"), ("to", "NOTIFY_TO")]:
        v = os.environ.get(env)
        if v:
            cfg[k] = v
    if CONFIG.exists():
        try:
            cfg.update(json.loads(CONFIG.read_text(encoding="utf-8")))
        except Exception as e:
            print(f"[warn] 读取 smtp.json 失败: {e}")
    return cfg


def main():
    if len(sys.argv) < 3:
        print("用法: notify_email.py <异常类型> <错误详情> [文案首句]")
        return 2
    err_type, detail = sys.argv[1], sys.argv[2]
    first_line = sys.argv[3] if len(sys.argv) > 3 else ""

    cfg = load_config()
    if not cfg.get("user") or not cfg.get("auth_code"):
        log = SKILL_DIR / "logs"
        log.mkdir(exist_ok=True)
        (log / "publish_errors.log").open("a", encoding="utf-8").write(
            f"[{datetime.now():%Y-%m-%d %H:%M}] {err_type} | {detail} | {first_line}\n")
        print("[error] SMTP 未配置，已写日志。请提供 163 授权码后重试。")
        return 1

    to = cfg.get("to") or cfg["user"]
    subject = f"【头条发布异常】{err_type}"
    body = (
        f"时间：{datetime.now():%Y-%m-%d %H:%M}\n"
        f"账号：棱镜折射\n"
        f"异常类型：{err_type}\n"
        f"文案首句：{first_line or '（无）'}\n"
        f"错误详情：{detail}\n"
        f"建议：检查浏览器登录态 / 重新扫码登录 / 手动发布。"
    )

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = cfg["user"]
    msg["To"] = to

    try:
        with smtplib.SMTP_SSL("smtp.163.com", 465, timeout=15) as s:
            s.login(cfg["user"], cfg["auth_code"])
            s.sendmail(cfg["user"], [to], msg.as_string())
        print(f"[ok] 邮件已发送到 {to}")
        return 0
    except Exception as e:
        log = SKILL_DIR / "logs"
        log.mkdir(exist_ok=True)
        (log / "publish_errors.log").open("a", encoding="utf-8").write(
            f"[{datetime.now():%Y-%m-%d %H:%M}] 邮件发送失败: {e}\n")
        print(f"[error] 邮件发送失败: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
