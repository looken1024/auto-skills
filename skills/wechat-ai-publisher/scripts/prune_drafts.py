#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""公众号草稿箱清理：删掉 N 天前的图集草稿，并把对应话题从话题池移除。

为什么要有它：图集 cron 每小时往草稿箱塞一条，两天就堆几十条；同时已用过的话题
应该从池子里摘掉，避免重复出图。

用法：
    python3 prune_drafts.py                    # 删 2 天前的图集草稿（默认）
    python3 prune_drafts.py --days 0           # 清空（连刚建的也删）
    python3 prune_drafts.py --dry-run          # 只报告，不删
    python3 prune_drafts.py --include-articles # 连手写文章一起删（默认保留）

设计约束：给 cron 的 no_agent 模式用 —— 只用标准库、不依赖 venv、stdout 即投递内容。
"""
import argparse
import json
import os
import re
import shutil
import time
import urllib.parse
import urllib.request
from datetime import datetime

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(SKILL_DIR, "scripts")
TOPICS_JSON = os.path.join(SCRIPTS, "topics.json")
GALLERY_PY = os.path.join(SCRIPTS, "pexels_gallery_draft.py")

API = "https://api.weixin.qq.com/cgi-bin"
# 图集标题格式：{话题}·每日图集（{日期}）
GALLERY_RE = re.compile(r"^(.+)·每日图集（\d{4}-\d{2}-\d{2}）$")


def load_env():
    cfg = {}
    p = os.path.join(SKILL_DIR, ".env")
    if os.path.exists(p):
        for line in open(p, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                cfg[k.strip()] = v.strip()
    return cfg


def api(path, body=None, token=None):
    url = f"{API}/{path}" + (f"?access_token={token}" if token else "")
    if body is None:
        req = urllib.request.Request(url, headers={"User-Agent": "prune/1.0"})
        raw = urllib.request.urlopen(req, timeout=60).read()
    else:
        req = urllib.request.Request(
            url, data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8",
                     "User-Agent": "prune/1.0"})
        raw = urllib.request.urlopen(req, timeout=60).read()
    return json.loads(raw.decode("utf-8"))


def list_drafts(token):
    out, offset = [], 0
    while True:
        d = api("draft/batchget", {"offset": offset, "count": 20, "no_content": 1}, token)
        if d.get("errcode"):
            raise RuntimeError(f"列草稿失败: {d}")
        items = d.get("item") or []
        if not items:
            break
        for it in items:
            if not (it.get("content") or {}).get("news_item"):
                continue
            ni = it["content"]["news_item"][0]
            out.append({"media_id": it["media_id"],
                        "type": ni.get("article_type") or "news",
                        "title": (ni.get("title") or "").strip(),
                        "update_time": it.get("update_time") or 0})
        offset += len(items)
        if offset >= (d.get("total_count") or 0):
            break
    return out


def topic_of(d):
    """图集草稿 → 话题名；不是图集返回 None。"""
    m = GALLERY_RE.match(d["title"])
    if m:
        return m.group(1)
    if d["type"] == "newspic":          # 旧版图片消息，标题就是话题
        return d["title"] or None
    return None


def sync_pool(removed):
    """把话题从 topics.json 和脚本内置表里摘掉，返回真正移除的列表。"""
    if not removed:
        return []
    pool = json.load(open(TOPICS_JSON, encoding="utf-8"))
    keep = [x for x in pool if x["cn"] not in removed]
    gone = sorted({x["cn"] for x in pool} & set(removed))
    if gone:
        ts = f"{datetime.now():%Y%m%d%H%M%S}"
        shutil.copy(TOPICS_JSON, f"{TOPICS_JSON}.bak-{ts}")
        shutil.copy(GALLERY_PY, f"{GALLERY_PY}.bak-{ts}")   # 两个源都留底，便于整体回滚
        json.dump(keep, open(TOPICS_JSON, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
        # 同步脚本内置兜底表（按行删，保留原注释与结构）
        src = open(GALLERY_PY, encoding="utf-8").read().split("\n")
        out, n = [], 0
        for ln in src:
            m = re.match(r'\s*\("([^"]+)",\s*"[^"]*"\),\s*$', ln)
            if m and m.group(1) in gone:
                n += 1
                continue
            out.append(ln)
        if n != len(gone):
            print(f"⚠️ 内置表只摘了 {n} 条、话题池摘了 {len(gone)} 条，请人工核对")
        open(GALLERY_PY, "w", encoding="utf-8").write("\n".join(out))
    return gone


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=2, help="删多少天前的（默认 2）")
    ap.add_argument("--dry-run", action="store_true", help="只报告不删")
    ap.add_argument("--include-articles", action="store_true",
                    help="连非图集草稿（手写文章）一起删；默认保留")
    a = ap.parse_args()

    cfg = load_env()
    tok = api("token", None) if False else json.loads(
        urllib.request.urlopen(urllib.request.Request(
            f"{API}/token?grant_type=client_credential"
            f"&appid={cfg.get('WECHAT_APP_ID','')}&secret={cfg.get('WECHAT_APP_SECRET','')}",
            headers={"User-Agent": "prune/1.0"}), timeout=60
        ).read().decode("utf-8"))["access_token"]

    drafts = list_drafts(tok)
    if not drafts:
        print("草稿箱是空的，无需清理。")
        return

    cutoff = time.time() - a.days * 86400
    targets = [d for d in drafts if d["update_time"] < cutoff]
    gallery = [d for d in targets if topic_of(d)]
    articles = [d for d in targets if not topic_of(d)]
    todo = gallery + (articles if a.include_articles else [])

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    if not todo:
        print(f"[{stamp}] 草稿箱 {len(drafts)} 条，没有超过 {a.days} 天的图集草稿，未做改动。")
        return

    if a.dry_run:
        print(f"[{stamp}] DRY-RUN 将删除 {len(todo)} 条"
              f"（图集 {len(gallery)}，文章 {len(todo)-len(gallery)}）：")
        for d in todo:
            print(f"  · {d['title']}")
        return

    deleted, failed = [], []
    for d in todo:
        r = api("draft/delete", {"media_id": d["media_id"]}, tok)
        (deleted if r.get("errcode") == 0 else failed).append(d)

    gone = sync_pool({t for t in (topic_of(d) for d in deleted) if t})

    print(f"[{stamp}] 草稿箱清理完成：原有 {len(drafts)} 条 → 删 {len(deleted)} 条"
          f"（图集 {len([d for d in deleted if topic_of(d)])}，"
          f"文章 {len([d for d in deleted if not topic_of(d)])}）")
    if articles and not a.include_articles:
        print(f"  保留 {len(articles)} 条手写文章（用 --include-articles 可一并删除）")
    if gone:
        print(f"  话题池移除 {len(gone)} 个关键词：" + "、".join(gone))
    else:
        print("  话题池无需改动")
    if failed:
        print(f"  ⚠️ {len(failed)} 条删除失败：" + "、".join(d["title"] for d in failed))


if __name__ == "__main__":
    main()
