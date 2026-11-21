#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""封面版式实验：main3（1 大 + 3 窄）/ three（3 条等宽）。

比六条等宽更稳：视觉重心在一张图上，竖条只当纹理，不会出现"多个太阳抢戏 + 六条地平线全断"。
"""
import argparse
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cover_card6_v4 import crop_fill, color_transfer, stats, pick
from PIL import Image, ImageDraw, ImageEnhance


def warm(canvas, amount=0.05):
    ov = Image.new("RGB", canvas.size, (255, 150, 80))
    return Image.blend(canvas, ov, amount)


def vignette(canvas, ratio=0.10, a_max=12):
    W, H = canvas.size
    d = ImageDraw.Draw(canvas, "RGBA")
    for y in range(int(H * ratio)):
        a = int(a_max * (1 - y / max(1, H * ratio)))
        d.line([(0, y), (W, y)], fill=(0, 0, 0, a))
        d.line([(0, H - 1 - y), (W, H - 1 - y)], fill=(0, 0, 0, a))
    return canvas


def build_main3(imgs, out, size=(1080, 648)):
    W, H = size
    items = [(p, Image.open(p).convert("RGB")) for p in imgs]
    scored = [(p, im, *stats(im)) for p, im in items]
    main = max(scored, key=lambda x: x[4])          # 饱和度最高当主图
    others = [x for x in scored if x[0] != main[0]]
    others = pick(others, 3)
    ref = main[1]

    canvas = Image.new("RGB", (W, H))
    mw = int(W * 0.62)
    canvas.paste(crop_fill(main[1], mw, H), (0, 0))

    sw = (W - mw) / max(1, len(others))
    for i, it in enumerate(others):
        x0 = int(mw + i * sw)
        tile = crop_fill(it[1], int(sw), H)
        tile = color_transfer(tile, ref)
        # 左边缘羽化 18px，与主图/前一条融合
        mask = Image.new("L", tile.size, 255)
        md = ImageDraw.Draw(mask)
        f = min(18, tile.width)
        for x in range(f):
            md.line([(x, 0), (x, H)], fill=int(255 * x / f))
        canvas.paste(tile, (x0 - f // 2, 0), mask)

    canvas = warm(canvas, 0.045)
    canvas = ImageEnhance.Contrast(canvas).enhance(1.04)
    canvas = vignette(canvas)
    canvas.save(out, quality=93)
    return out


def build_three(imgs, out, size=(1080, 648)):
    W, H = size
    items = [(p, Image.open(p).convert("RGB")) for p in imgs]
    scored = [(p, im, *stats(im)) for p, im in items]
    sel = pick(scored, 3)
    ref = max(sel, key=lambda x: x[4])[1]
    canvas = Image.new("RGB", (W, H))
    sw = W / len(sel)
    for i, it in enumerate(sel):
        x0 = int(i * sw)
        tile = crop_fill(it[1], int(sw), H)
        tile = color_transfer(tile, ref)
        mask = Image.new("L", tile.size, 255)
        md = ImageDraw.Draw(mask)
        f = min(24, tile.width) if i else 0
        for x in range(f):
            md.line([(x, 0), (x, H)], fill=int(255 * x / f))
        canvas.paste(tile, (x0 - f // 2, 0), mask)
    canvas = warm(canvas, 0.05)
    canvas = ImageEnhance.Contrast(canvas).enhance(1.04)
    canvas = vignette(canvas)
    canvas.save(out, quality=93)
    return out



def build_grid(imgs, out, size=(1080, 648)):
    """左大图 + 右侧 2×2 小图网格：小图不再被压成细条。"""
    W, H = size
    items = [(p, Image.open(p).convert("RGB")) for p in imgs]
    scored = [(p, im, *stats(im)) for p, im in items]
    main = max(scored, key=lambda x: x[4])
    others = pick([x for x in scored if x[0] != main[0]], 4)
    ref = main[1]
    canvas = Image.new("RGB", (W, H))
    mw = int(W * 0.62)
    canvas.paste(crop_fill(main[1], mw, H), (0, 0))
    gw = (W - mw) / 2
    gh = H / 2
    for i, it in enumerate(others[:4]):
        col, row = i % 2, i // 2
        tile = crop_fill(it[1], int(gw), int(gh))
        tile = color_transfer(tile, ref)
        canvas.paste(tile, (int(mw + col * gw), int(row * gh)))
    # 极细分割线
    d = ImageDraw.Draw(canvas)
    d.line([(mw, 0), (mw, H)], fill=(255, 245, 235), width=2)
    d.line([(mw + gw, 0), (mw + gw, H)], fill=(255, 245, 235), width=2)
    d.line([(mw, gh), (W, gh)], fill=(255, 245, 235), width=2)
    canvas = warm(canvas, 0.045)
    canvas = ImageEnhance.Contrast(canvas).enhance(1.03)
    canvas = vignette(canvas)
    canvas.save(out, quality=93)
    return out

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--imgs", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--layout", choices=["main3", "three", "grid"], default="main3")
    ap.add_argument("--size", default="1080x648")
    a = ap.parse_args()
    imgs = [x.strip() for x in a.imgs.split(",") if x.strip()]
    W, H = [int(x) for x in a.size.lower().split("x")]
    fn = {"main3": build_main3, "three": build_three, "grid": build_grid}[a.layout]
    print(fn(imgs, a.out, (W, H)))
