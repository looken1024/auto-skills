#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""图集封面 v2：六条竖拼（或 N 条），自动按色相排序 + 统一调色，改善色彩过渡。

用法:
  python3 cover_card6_v2.py --imgs a.jpg,b.jpg,... --out cover.jpg \
      --n 6 --size 1080x648 --sort hue --grade 0.55
"""
import argparse, colorsys, os
from PIL import Image, ImageEnhance, ImageDraw

BG = (255, 255, 255)


def fit_cover(im, w, h):
    iw, ih = im.size
    s = max(w / iw, h / ih)
    im = im.resize((int(iw * s + 0.5), int(ih * s + 0.5)), Image.LANCZOS)
    x = (im.width - w) // 2
    y = (im.height - h) // 2
    return im.crop((x, y, x + w, y + h))


def stats(im):
    small = im.convert("RGB").resize((48, 48))
    px = list(small.getdata())
    n = len(px)
    r = sum(p[0] for p in px) / n / 255
    g = sum(p[1] for p in px) / n / 255
    b = sum(p[2] for p in px) / n / 255
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    return h * 360, l, s


def unify(im, target_l, strength=0.5):
    """把亮度往目标值拉、饱和度略收，减少各条之间的跳变。"""
    im = im.convert("RGB")
    h, l, s = stats(im)
    # 亮度
    if l > 0.01:
        f = 1 + (target_l / l - 1) * strength
        im = ImageEnhance.Brightness(im).enhance(max(0.6, min(1.6, f)))
    # 饱和度：向 0.85 靠
    im = ImageEnhance.Color(im).enhance(1 - 0.35 * strength)
    return im


def build(imgs, out, n=6, size=(1080, 648), sort="hue", grade=0.55):
    W, H = size
    items = [(p, Image.open(p).convert("RGB")) for p in imgs]
    # 按色相排序，形成连续光谱；色相接近时按亮度微调
    if sort == "hue":
        items.sort(key=lambda x: (stats(x[1])[0], stats(x[1])[1]))
    elif sort == "bright":
        items.sort(key=lambda x: stats(x[1])[1])
    items = items[:n]
    target_l = sum(stats(im)[1] for _, im in items) / len(items)

    canvas = Image.new("RGB", (W, H), BG)
    strip_w = W / len(items)
    for i, (p, im) in enumerate(items):
        x0, x1 = int(round(i * strip_w)), int(round((i + 1) * strip_w))
        tile = fit_cover(im, x1 - x0, H)
        tile = unify(tile, target_l, strength=grade)
        canvas.paste(tile, (x0, 0))

    # 整体统一：轻微暖色 + 顶部/底部微暗角，让色块像一张图
    overlay = Image.new("RGB", (W, H), (255, 148, 70))
    canvas = Image.blend(canvas, overlay, 0.07 * grade)

    # 极轻的上下暗角
    d = ImageDraw.Draw(canvas, "RGBA")
    for y in range(int(H * 0.12)):
        a = int(14 * (1 - y / max(1, H * 0.12)))
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
    ap.add_argument("--sort", choices=["hue", "bright", "none"], default="hue")
    ap.add_argument("--grade", type=float, default=0.55)
    a = ap.parse_args()
    imgs = [x.strip() for x in a.imgs.split(",") if x.strip()]
    W, H = [int(x) for x in a.size.lower().split("x")]
    print(build(imgs, a.out, a.n, (W, H), a.sort, a.grade))
