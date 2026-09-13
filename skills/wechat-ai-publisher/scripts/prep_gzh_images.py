#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""为重写好的公众号文章准备封面（2.35:1）和正文图（16:9），素材来自 Pexels"""
import os, sys, json
from PIL import Image

SCRIPTS = os.path.expanduser("~/.hermes/skills/wechat-ai-publisher/scripts")
sys.path.insert(0, SCRIPTS)
import pexels_gallery_draft as P

print("Pexels 配置:", P.PEXELS_CFG, "存在:", os.path.exists(P.PEXELS_CFG))

def pick(query, want_landscape=True, n=1):
    photos = P.pexels_search(query, per_page=30)
    out = []
    for p in photos:
        w, h = p.get("width", 0), p.get("height", 0)
        if want_landscape and w < h:
            continue
        if w < 1200:
            continue
        out.append(p)
        if len(out) >= n:
            break
    return out

# 封面：日历 / 办公桌 / 周末感
cands = pick("calendar on desk office", n=3)
if not cands:
    cands = pick("office desk clock", n=3)
print("封面候选:", [(c["id"], c.get("width"), c.get("height")) for c in cands])
if cands:
    P.pexels_fetch(cands[0]["id"], "/tmp/gzh_cover_raw.jpg")
    print("封面原图:", Image.open("/tmp/gzh_cover_raw.jpg").size)

    # 裁成公众号头图比例 2.35:1 → 940x400
    im = Image.open("/tmp/gzh_cover_raw.jpg").convert("RGB")
    W, H = im.size
    target_ratio = 2.35
    if W / H > target_ratio:
        new_w = int(H * target_ratio)
        left = (W - new_w) // 2
        im2 = im.crop((left, 0, left + new_w, H))
    else:
        new_h = int(W / target_ratio)
        top = int((H - new_h) * 0.35)   # 稍微留天头
        im2 = im.crop((0, top, W, top + new_h))
    im2 = im2.resize((940, 400), Image.LANCZOS)
    im2.save("/tmp/gzh_cover.jpg", "JPEG", quality=90)
    print("封面成品:", Image.open("/tmp/gzh_cover.jpg").size, "%.0fKB" % (os.path.getsize("/tmp/gzh_cover.jpg")/1024))

# 正文图：工位 / 通勤 / 加班夜景
c2 = pick("empty office at night desk lamp", n=3)
if not c2:
    c2 = pick("weekend relax coffee window", n=3)
print("正文图候选:", [(c["id"], c.get("width"), c.get("height")) for c in c2])
if c2:
    P.pexels_fetch(c2[0]["id"], "/tmp/gzh_body_raw.jpg")
    im = Image.open("/tmp/gzh_body_raw.jpg").convert("RGB")
    W, H = im.size
    tw, th = 1080, 608
    if W / H > tw / th:
        nw = int(H * tw / th); l = (W - nw) // 2; im = im.crop((l, 0, l + nw, H))
    else:
        nh = int(W * th / tw); t = int((H - nh) * 0.4); im = im.crop((0, t, W, t + nh))
    im = im.resize((tw, th), Image.LANCZOS)
    im.save("/tmp/gzh_body.jpg", "JPEG", quality=88)
    print("正文图成品:", Image.open("/tmp/gzh_body.jpg").size, "%.0fKB" % (os.path.getsize("/tmp/gzh_body.jpg")/1024))

# 明暗自检（防废图）
for f in ("/tmp/gzh_cover.jpg", "/tmp/gzh_body.jpg"):
    if os.path.exists(f):
        g = Image.open(f).convert("L"); h = g.histogram(); t = g.width*g.height
        print(f, "暗像素 %.1f%% / 亮像素 %.1f%%" % (sum(h[:85])/t*100, sum(h[170:])/t*100))
