#!/usr/bin/env python3
import json, urllib.request, re, sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

cfg = config.get_wechat_config()
APP_ID = cfg['app_id']
APP_SECRET = cfg['app_secret']

def get_token():
    url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={APP_ID}&secret={APP_SECRET}"
    with urllib.request.urlopen(url, timeout=30) as r:
        d = json.loads(r.read().decode('utf-8'))
    return d['access_token']

tok = get_token()
url = f"https://api.weixin.qq.com/cgi-bin/draft/batchget?access_token={tok}"
body = {"offset": 0, "count": 20, "no_content": 0}
req = urllib.request.Request(url, data=json.dumps(body, ensure_ascii=False).encode('utf-8'),
    headers={"Content-Type": "application/json"})
with urllib.request.urlopen(req, timeout=30) as r:
    raw = r.read()

# 正确解码 UTF-8 字节
data = json.loads(raw.decode('utf-8'))

for item in data.get('item', []):
    mid = item.get('media_id','')
    for news in item.get('content', {}).get('news_item', []):
        title = news.get('title','')
        thumb = news.get('thumb_media_id','')
        content = news.get('content','')
        imgs = len(re.findall(r'<img', content))
        print(f"media_id={mid}")
        print(f"  title={title}")
        print(f"  thumb_media_id={'✅非空' if thumb else '❌空'}")
        print(f"  正文 img 数量={imgs}")
        print()
