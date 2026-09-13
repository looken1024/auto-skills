#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按 skill 要求，用 draft/batchget 验证刚建的草稿（字节级解码，避免中文假乱码）"""
import json, sys, os
sys.path.insert(0, os.path.expanduser("~/.hermes/skills/wechat-ai-publisher/scripts"))
import requests
from config import get_wechat_config

cfg = get_wechat_config()
tok = requests.get("https://api.weixin.qq.com/cgi-bin/token",
                   params={"grant_type": "client_credential", "appid": cfg["app_id"], "secret": cfg["app_secret"]},
                   timeout=20).json().get("access_token")
print("token:", bool(tok))
r = requests.post(f"https://api.weixin.qq.com/cgi-bin/draft/batchget?access_token={tok}",
                  data=json.dumps({"offset": 0, "count": 5, "no_content": 0}).encode(), timeout=30)
d = json.loads(r.content.decode("utf-8"))
print("草稿总数:", d.get("total_count"))
for it in d.get("item", [])[:3]:
    for ni in it.get("content", {}).get("news_item", []):
        html = ni.get("content") or ""
        print("-", ni.get("title"))
        print("   type:", ni.get("article_type"), "| 正文 <img>:", html.count("<img"),
              "| 正文长度:", len(html), "| 封面:", bool(ni.get("thumb_url")),
              "| 摘要:", (ni.get("digest") or "")[:40])
