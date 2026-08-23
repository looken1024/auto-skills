#!/bin/bash
# vl_check.sh —— 用 qwen-vl-max 批量验证素材图片内容
# 用法: bash vl_check.sh img1.jpg [img2.jpg ...]
# 依赖: ~/.openclaw/openclaw.json 中 dashscope apiKey
python3 - "$@" <<'PY'
import json, base64, os, sys, urllib.request

key = json.load(open(os.path.expanduser("~/.openclaw/openclaw.json")))["models"]["providers"]["dashscope"]["apiKey"]

def ask_vl(img_path, question):
    with open(img_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    body = {"model": "qwen-vl-max", "input": {"messages": [{"role": "user", "content": [
        {"image": f"data:image/jpeg;base64,{b64}"}, {"text": question}]}]}}
    req = urllib.request.Request(
        "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        d = json.loads(r.read())
    c = d["output"]["choices"][0]["message"]["content"]
    return "".join(x.get("text","") for x in c) if isinstance(c, list) else c

for p in sys.argv[1:]:
    print(f"=== {p} ===")
    print(ask_vl(p, "一句话描述画面内容：主体是什么？清晰度如何？适合做竖版科普短视频素材吗？"))
PY