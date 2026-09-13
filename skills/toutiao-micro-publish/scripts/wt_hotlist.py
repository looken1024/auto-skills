#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""取热榜（全脚本化，不依赖 agent）：优先用真实浏览器里的同源 fetch 拿 JSON，退化到 DOM 抓取。

输出：/tmp/wt_hot.json  [{title, source, url}]，stdout 打印前 N 条。
用法：python3 wt_hotlist.py [--top 30] [--out /tmp/wt_hot.json]
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wt_common import cdp_tab  # noqa: E402


def try_toutiao(cdp):
    """头条热榜：在同一浏览器里 fetch 官方 JSON 接口（同源，成功率高）"""
    cdp.goto("https://www.toutiao.com/", wait=5)
    js = ("(async () => { try { const r = await fetch('https://www.toutiao.com/hot-event/hot-board/"
          "?origin=toutiao_pc', {credentials:'include'}); const j = await r.json();"
          "return JSON.stringify((j.data||[]).map(x=>({title:x.Title, url:x.Url, hot:x.HotValue}))); }"
          " catch(e) { return 'ERR:'+e.message; } })()")
    out = cdp.js(js, timeout_ms=40000)
    if not out or out.startswith("ERR:"):
        return []
    try:
        items = json.loads(out)
    except Exception:
        return []
    return [{"title": i["title"], "source": "头条热榜", "url": i.get("url") or ""} for i in items if i.get("title")]


def try_baidu(cdp):
    """百度热搜：DOM 抓取（页面是 SSR，标题在 .c-single-text-ellipsis）"""
    cdp.goto("https://top.baidu.com/board?tab=realtime", wait=6)
    js = ("(() => { const a=[...document.querySelectorAll('div[class*=c-single-text-ellipsis]')];"
          "return JSON.stringify(a.map(e=>e.innerText.trim()).filter(Boolean).slice(0,50)); })()")
    out = cdp.js(js)
    try:
        ts = json.loads(out or "[]")
    except Exception:
        ts = []
    return [{"title": t, "source": "百度热搜", "url": ""} for t in ts]


def try_tophub(cdp):
    """tophub 微博热搜榜：DOM 抓取"""
    cdp.goto("https://tophub.today/n/KqndgxeLl9", wait=7)
    js = ("(() => { const a=[...document.querySelectorAll('td.al a, .cc-cd-cb a')];"
          "return JSON.stringify(a.map(e=>e.innerText.trim()).filter(t=>t.length>4).slice(0,50)); })()")
    out = cdp.js(js)
    try:
        ts = json.loads(out or "[]")
    except Exception:
        ts = []
    return [{"title": t, "source": "微博热搜(tophub)", "url": ""} for t in ts]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=30)
    ap.add_argument("--out", default="/tmp/wt_hot.json")
    a = ap.parse_args()

    cdp, _ = cdp_tab(prefer_host=None, new_url="about:blank")
    allitems, tried = [], []
    for name, fn in (("头条热榜", try_toutiao), ("百度热搜", try_baidu), ("微博热搜", try_tophub)):
        try:
            got = fn(cdp)
        except Exception as e:
            got = []
            print(f"[hot] {name} 异常 {type(e).__name__}: {str(e)[:80]}", file=sys.stderr)
        tried.append(f"{name}={len(got)}")
        allitems += got
        if len(allitems) >= a.top:
            break
    cdp.close()

    # 去重 + 过滤明显不适合的条目
    seen, kept = set(), []
    bad = ("案", "杀", "身亡", "遇难", "猝死", "地震", "去世", "讣告", "枪击", "坠亡", "轻生", "自杀")
    for it in allitems:
        t = it["title"].strip()
        if not t or t in seen:
            continue
        seen.add(t)
        if any(b in t for b in bad):
            continue
        kept.append(it)
        if len(kept) >= a.top:
            break

    json.dump(kept, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"[hot] 来源尝试: {', '.join(tried)} -> 去重后 {len(kept)} 条 -> {a.out}", file=sys.stderr)
    for i, it in enumerate(kept[:a.top], 1):
        print(f"{i:2d}. [{it['source']}] {it['title']}")


if __name__ == "__main__":
    main()
