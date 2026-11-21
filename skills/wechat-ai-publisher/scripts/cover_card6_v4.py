#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""图集封面 v4：色彩迁移 + 收紧选图 + 无白缝羽化。

关键改进（针对"色彩过渡不好看"）：
1. 收紧选图：只要暖色、饱和度够、亮度在同一档的图；
2. Reinhard 色彩迁移：把每条图的 RGB 均值和方差对齐到参考图，色调真正统一；
3. 底层先铺满参考图，再叠条，接缝不会露出白线；
4. 大羽化（24px）+ 整体渐变，视觉上连成一片。
"""
import argparse
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance
import colorsys


def stats(im):
    px = np.asarray(im.convert("RGB").resize((64, 64)), dtype=np.float32) / 255.0
    px = px.reshape(-1, 3)
    r, g, b = px.mean(axis=0)
    h, l, s = colorsys.rgb_to_hls(float(r), float(g), float(b))
    return h * 360, l, s


def color_transfer(src, ref):
    """把 src 的 RGB 均值/方差对齐到 ref（Reinhard 简化版）。"""
    s = np.asarray(src, dtype=np.float32)
    r = np.asarray(ref.resize(src.size), dtype=np.float32)
    for c in range(3):
        sm, ss = s[:, :, c].mean(), s[:, :, c].std()
        rm, rs = r[:, :, c].mean(), r[:, :, c].std()
        s[:, :, c] = (s[:, :, c] - sm) * (rs / max(ss, 1e-6)) + rm
    return Image.fromarray(np.clip(s, 0, 255).astype(np.uint8))


def horizon_ratio(im):
    g = np.asarray(im.convert("L").resize((192, 192)), dtype=np.float32)
    d = np.abs(np.diff(g, axis=0)).mean(axis=1)
    d = np.convolve(d, np.ones(7) / 7, mode="same")
    lo, hi = int(len(d) * 0.15), int(len(d) * 0.85)
    return (lo + int(np.argmax(d[lo:hi]))) / len(d)


def crop_fill(src, w, h, horizon_at=0.46):
    iw, ih = src.size
    ratio = horizon_ratio(src)
    s = max(w / iw, h / ih)
    im = src.resize((int(iw * s + 0.5), int(ih * s + 0.5)), Image.LANCZOS)
    top = int(ratio * im.height - h * horizon_at)
    top = max(0, min(im.height - h, top))
    left = (im.width - w) // 2
    return im.crop((left, top, left + w, top + h))


def pick(items, n):
    """暖色 + 饱和 + 亮度同一档；不够时逐级放宽。"""
    def is_warm(x):
        h, l, s = x[2], x[3], x[4]
        return (h < 70 or h > 320) and s > 0.20 and 0.22 < l < 0.52
    sel = [x for x in items if is_warm(x)]
    if len(sel) < n:
        sel = [x for x in items if (x[2] < 70 or x[2] > 320) and x[4] > 0.18]
    if len(sel) < n:
        sel = items
    return sel[:n]


def build(imgs, out, n=6, size=(1080, 648), feather=24, horizon_at=0.46):
    W, H = size
    items = []
    for p in imgs:
        im = Image.open(p).convert("RGB")
        h, l, s = stats(im)
        items.append((p, im, h, l, s))
    sel = pick(items, n)
    # 参考图：亮度居中、饱和度最高的一张
    ref = max(sel, key=lambda x: x[4])[1]

    canvas = Image.new("RGB", (W, H), (20, 12, 8))
    canvas.paste(crop_fill(ref, W, H, horizon_at), (0, 0))  # 先铺底，防白缝

    strip_w = W / len(sel)
    for i, (p, im, _, _, _) in enumerate(sel):
        x0, x1 = int(round(i * strip_w)), int(round((i + 1) * strip_w))
        tile = crop_fill(im, x1 - x0, H, horizon_at)
        tile = color_transfer(tile, ref)
        if i == 0:
            canvas.paste(tile, (0, 0))
        else:
            mask = Image.new("L", tile.size, 255)
            md = ImageDraw.Draw(mask)
            f = min(feather, tile.width)
            for x in range(f):
                md.line([(x, 0), (x, H)], fill=int(255 * x / f))
            canvas.paste(tile, (x0 - f // 2, 0), mask)

    # 统一氛围：暖色轻叠 + 对比 + 上下极轻暗角
    warm = Image.new("RGB", (W, H), (255, 150, 80))
    canvas = Image.blend(canvas, warm, 0.05)
    canvas = ImageEnhance.Contrast(canvas).enhance(1.04)
    d = ImageDraw.Draw(canvas, "RGBA")
    for y in range(int(H * 0.10)):
        a = int(12 * (1 - y / max(1, H * 0.10)))
        d.line([(0, y), (W, y)], fill=(0, 0, 0, a))
        d.line([(0, H - 1 - y), (W, H - 1 - y)], fill=(0, 0, 0, a))

    canvas.save(out, quality=93)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--imgs", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--n", type=int, default=6)
    ap.add_argument("--size", default="1080x648")
    ap.add_argument("--feather", type=int, default=24)
    a = ap.parse_args()
    imgs = [x.strip() for x in a.imgs.split(",") if x.strip()]
    W, H = [int(x) for x in a.size.lower().split("x")]
    print(build(imgs, a.out, a.n, (W, H), a.feather))
