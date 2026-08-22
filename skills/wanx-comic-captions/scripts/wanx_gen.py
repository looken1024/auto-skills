#!/usr/bin/env python3
"""通义万相(wanx2.1)文生图：竖版双格治愈漫画。
用法: python3 wanx_gen.py '<prompt>' <out.png>
API Key 从 ~/.openclaw/openclaw.json 的 dashscope provider 真实读取。
"""
import json, sys, time, subprocess, os, urllib.request

CONFIG = os.path.expanduser("~/.openclaw/openclaw.json")

def find_dashscope_key(o):
    if isinstance(o, dict):
        if isinstance(o.get("baseUrl"), str) and "dashscope" in o["baseUrl"] and "apiKey" in o:
            return o["apiKey"]
        for v in o.values():
            r = find_dashscope_key(v)
            if r:
                return r
    elif isinstance(o, list):
        for v in o:
            r = find_dashscope_key(v)
            if r:
                return r
    return None

KEY = find_dashscope_key(json.load(open(CONFIG)))
if not KEY:
    print("ERROR: 未找到 DashScope API Key")
    sys.exit(1)

URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis"

def submit(prompt, size="1024*1440"):
    payload = {"model": "wanx2.1-t2i-turbo", "input": {"prompt": prompt},
               "parameters": {"size": size, "n": 1, "prompt_extend": True}}
    h = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json",
         "X-DashScope-Async": "enable"}
    req = urllib.request.Request(URL, data=json.dumps(payload).encode(), headers=h, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return {"HTTPError": e.code, "body": e.read().decode()[:600]}

def poll(task_id):
    for _ in range(60):
        req = urllib.request.Request(f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}",
                                     headers={"Authorization": f"Bearer {KEY}"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            r = json.loads(resp.read().decode())
        st = r["output"].get("task_status")
        if st == "SUCCEEDED":
            return r["output"]["results"][0]["url"]
        if st in ("FAILED", "CANCELED", "UNKNOWN"):
            print("FAIL:", json.dumps(r, ensure_ascii=False)[:800])
            sys.exit(1)
        time.sleep(4)
    print("超时")
    sys.exit(1)

if __name__ == "__main__":
    prompt, out = sys.argv[1], sys.argv[2]
    r = submit(prompt)
    task = r.get("output", {}).get("task_id")
    if not task:
        print("NO TASK", json.dumps(r, ensure_ascii=False)[:600])
        sys.exit(1)
    url = poll(task)
    subprocess.run(["curl", "-s", "-o", out, url], check=True)
    print("SAVED", out)
