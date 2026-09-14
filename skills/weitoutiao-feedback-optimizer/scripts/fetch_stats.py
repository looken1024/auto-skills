#!/usr/bin/env python3
"""抓取头条创作后台微头条列表的真实数据（展现/阅读/点赞/评论），追加到 data/stats.jsonl。

用法: python3 fetch_stats.py
退出码: 0=成功 2=未登录或浏览器不可用 3=解析失败
"""
import json, re, sys, time
from pathlib import Path
from datetime import datetime

import requests
import websocket

CDP = "http://127.0.0.1:9222"
LIST_URL = "https://mp.toutiao.com/profile_v4/weitoutiao"
HERE = Path(__file__).resolve().parent.parent
DATA = HERE / "data" / "stats.jsonl"


def cdp_ws(tid, expr, timeout=25):
    url = f"ws://127.0.0.1:9222/devtools/page/{tid}"
    ws = websocket.create_connection(url, timeout=timeout, suppress_origin=True)
    ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                        "params": {"expression": expr, "returnByValue": True}}))
    while True:
        m = json.loads(ws.recv())
        if m.get("id") == 1:
            ws.close()
            return m["result"].get("result", {}).get("value")


def main():
    try:
        tabs = [t for t in requests.get(CDP + "/json", timeout=5).json() if t["type"] == "page"]
    except Exception as e:
        print(f"浏览器不可用: {e}"); sys.exit(2)
    if not tabs:
        print("无可用标签页"); sys.exit(2)
    tid = tabs[0]["id"]
    cdp_ws(tid, f"location.href='{LIST_URL}'")
    time.sleep(8)
    txt = cdp_ws(tid, "document.body.innerText") or ""
    if "已发布" not in txt or "展现" not in txt:
        print("页面未渲染或未登录（无已发布/展现字样）"); sys.exit(2)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows = []
    for seg in txt.split("\n展开\n")[1:]:
        d = re.search(r"展现 (\d+)阅读 (\d+)点赞 (\d+)评论 (\d+)", seg)
        t = re.search(r"(\d{2}-\d{2} \d{2}:\d{2})", seg)
        if not (d and t):
            continue
        body_first = seg.split("\n")[0].strip()[:80]
        pub = f"{datetime.now().year}-{t.group(1)}"
        rows.append({"fetched_at": now, "published_at": pub,
                     "impressions": int(d.group(1)), "reads": int(d.group(2)),
                     "likes": int(d.group(3)), "comments": int(d.group(4)),
                     "first_line": body_first})
    if not rows:
        print("解析到 0 条"); sys.exit(3)

    DATA.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA, "a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"OK 追加 {len(rows)} 条到 {DATA}")


if __name__ == "__main__":
    main()
