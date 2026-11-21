#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""图集封面 v3：同色系选图 + 地平线对齐 + 色温统一 + 接缝羽化。

比 v2 多做的三件事：
1. 只保留同一色系（默认暖色）的图，避免冷暖硬撞；
2. 检测每条图的水天线，统一放到画面同一高度；
3. 条与条之间 10px 渐变羽化，并在整体上做色温/亮度归一。
"""
import argparse, colorsys
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance


def stats(im):
    small = im.convert("RGB").resize((64, 64))
    px = np.asarray(small, dtype=np.float32).reshape(-1, 3) / 255.0
    r, g, b = px.mean(axis=0)
    h, l, s = colorsys.rgb_to_hls(float(r), float(g), float(b))
    return h * 360, l, s, (r, g, b)


def horizon_ratio(im):
    """用行方向梯度找水天线，返回相对高度 0-1。"""
    g = np.asarray(im.convert("L").resize((192, 192)), dtype=np.float32)
    d = np.abs(np.diff(g, axis=0)).mean(axis=1)
    k = np.ones(7) / 7
    d = np.convolve(d, k, mode="same")
    # 找上半部到中下部之间最强的水平边缘
    lo, hi = int(len(d) * 0.15), int(len(d) * 0.85)
    idx = lo + int(np.argmax(d[lo:hi]))
    return idx / len(d)


def crop_fill(src, w, h, horizon_at=0.45):
    """等比放大到填满，垂直方向按地平线对齐裁剪。"""
    iw, ih = src.size
    ratio = horizon_ratio(src)
    s = max(w / iw, h / ih)
    im = src.resize((int(iw * s + 0.5), int(ih * s + 0.5)), Image.LANCZOS)
    hy = ratio * im.height
    top = int(hy - h * horizon_at)
    top = max(0, min(im.height - h, top))
    left = (im.width - w) // 2
    return im.crop((left, top, left + w, top + h))


def warm_unify(im, target_l, warmth=1.0):
    """统一亮度 + 轻微暖调（拉红、压蓝）。"""
    im = im.convert("RGB")
    _, l, _, _ = stats(im)
    if l > 0.02:
        f = 1 + (target_l / l - 1) * 0.6
        im = ImageEnhance.Brightness(im).enhance(max(0.7, min(1.45, f)))
    im = ImageEnhance.Color(im).enhance(0.92)
    r, g, b = im.split()
    r = r.point(lambda v: min(255, int(v * (1 + 0.045 * warmth))))
    b = b.point(lambda v: int(v * (1 - 0.05 * warmth)))
    return Image.merge("RGB", (r, g, b))


def build(imgs, out, n=6, size=(1080, 648), warm_only=True, feather=12, horizon_at=0.45):
    W, H = size
    items = []
    for p in imgs:
        im = Image.open(p).convert("RGB")
        h, l, s, _ = stats(im)
        items.append((p, im, h, l, s))
    if warm_only:
        warm = [x for x in items if (x[2] < 70 or x[2] > 320) and x[4] > 0.10]
        if len(warm) >= n:
            items = warm
    items.sort(key=lambda x: (x[2], x[3]))
    items = items[:n]
    target_l = float(np.mean([x[3] for x in items]))

    canvas = Image.new("RGB", (W, H), (255, 255, 255))
    strip_w = W / len(items)
    for i, (p, im, _, _, _) in enumerate(items):
        x0, x1 = int(round(i * strip_w)), int(round((i + 1) * strip_w))
        tile = crop_fill(im, x1 - x0, H, horizon_at)
        tile = warm_unify(tile, target_l)
        if i == 0:
            canvas.paste(tile, (x0, 0))
        else:
            mask = Image.new("L", tile.size, 255)
            md = ImageDraw.Draw(mask)
            for x in range(min(feather, tile.width)):
                md.line([(x, 0), (x, H)], fill=int(255 * x / max(1, feather)))
            canvas.paste(tile, (x0 - feather // 2, 0), mask)

    # 整体再拉一次色温，统一氛围
    r, g, b = canvas.split()
    r = r.point(lambda v: min(255, int(v * 1.035)))
    b = b.point(lambda v: int(v * 0.965))
    canvas = Image.merge("RGB", (r, g, b))
    canvas = ImageEnhance.Contrast(canvas).enhance(1.03)
    canvas.save(out, quality=93)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--imgs", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--n", type=int, default=6)
    ap.add_argument("--size", default="1080x648")
    ap.add_argument("--all-colors", action="store_true")
    a = ap.parse_args()
    imgs = [x.strip() for x in a.imgs.split(",") if x.strip()]
    W, H = [int(x) for x in a.size.lower().split("x")]
    print(build(imgs, a.out, a.n, (W, H), warm_only=not a.all_colors))
