#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""删除指定草稿（draft/delete）。用法：python3 delete_draft.py <media_id> [media_id2 ...]"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import requests
from config import get_wechat_config

cfg = get_wechat_config()
tok = requests.get("https://api.weixin.qq.com/cgi-bin/token",
                   params={"grant_type": "client_credential", "appid": cfg["app_id"], "secret": cfg["app_secret"]},
                   timeout=20).json().get("access_token")
if not tok:
    print("拿 token 失败"); sys.exit(1)
ids = sys.argv[1:]
if not ids:
    print("需要 media_id 参数"); sys.exit(1)
r = requests.post(f"https://api.weixin.qq.com/cgi-bin/draft/delete?access_token={tok}",
                  data=json.dumps({"media_id": ids[0]}).encode(), timeout=30)
print("删除", ids[0], "->", r.content.decode("utf-8"))
