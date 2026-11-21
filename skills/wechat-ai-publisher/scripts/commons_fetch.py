#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 Wikimedia Commons 抓一批图（走代理），处理后做 QC，供公众号图集使用。

用法:
  python3 commons_fetch.py --cands cands.json --outdir /tmp/yy_out --max 14
cands.json: [{title, lic, w, h, thumb}, ...]
"""
import argparse, json, os, sys, time, urllib.request
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pexels_gallery_draft as P

PROXY = {"http": "http://127.0.0.1:9981", "https": "http://127.0.0.1:9981"}
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler(PROXY))


def fetch(url, dst):
    req = urllib.request.Request(url, headers={"User-Agent": "HermesBot/1.0 (local use)"})
    with OPENER.open(req, timeout=90) as r:
        data = r.read()
    open(dst, "wb").write(data)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cands", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--max", type=int, default=14)
    ap.add_argument("--topic", default="")
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)
    cands = json.load(open(a.cands, encoding="utf-8"))
    for c in cands:
        c["title"] = c.get("title") or c.get("t") or ""
    rows, ok = [], 0
    for i, c in enumerate(cands, 1):
        if ok >= a.max:
            break
        raw = os.path.join(a.outdir, f"raw_{i}.jpg")
        out = os.path.join(a.outdir, f"img_{i}.jpg")
        try:
            fetch(c["thumb"], raw)
            P.process_image(raw, out)
            good, why = P.image_quality_ok(out, a.topic or c.get("term", ""))
        except Exception as e:
            print(f"{i} ERR {e}")
            continue
        if not good:
            print(f"{i} 剔除({why}) {c['title'][:60]}")
            os.remove(out)
            continue
        ok += 1
        rows.append({**c, "file": out})
        print(f"{i} OK {c['w']}x{c['h']} {c['lic']} | {c['title'][:60]}")
        time.sleep(0.4)
    json.dump(rows, open(os.path.join(a.outdir, "picked.json"), "w"), ensure_ascii=False, indent=1)
    print(f"\n合格 {ok} 张")


if __name__ == "__main__":
    main()
