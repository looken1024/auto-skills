#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""图集封面·六格竖条卡片（参考公众号资讯卡片样式）

白底卡片 + 顶部黑色标题 + 6 条竖图满铺 + 图上左下角地名。

用法:
  python3 cover_card6.py --title "华山 长空栈道挂在崖壁上" --place "华山" \
      --imgs a.jpg,b.jpg,c.jpg,d.jpg,e.jpg,f.jpg --out card.jpg [--size 1080x648]
"""
import argparse, os
from PIL import Image, ImageDraw, ImageFont

FONT_BOLD = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"
BG = (255, 255, 255)
INK = (20, 20, 20)
PAD_TOP = 0.09          # 标题区高度占比
IMG_TOP = 0.24          # 图片区起点
SIDE = 0.0              # 图片区左右留白（0 = 满铺）


def fit_cover(im, w, h):
    """等比裁剪填满 w×h。"""
    iw, ih = im.size
    s = max(w / iw, h / ih)
    im = im.resize((int(iw * s + 0.5), int(ih * s + 0.5)), Image.LANCZOS)
    x = (im.width - w) // 2
    y = (im.height - h) // 2
    return im.crop((x, y, x + w, y + h))


def build(title, place, imgs, out, size=(1080, 648), no_text=False):
    W, H = size
    canvas = Image.new("RGB", (W, H), BG)

    if no_text:
        # 纯图版：六条竖图满铺，不加标题和地名
        top, img_h = 0, H
        n = len(imgs)
        strip_w = W / n
        for i, p in enumerate(imgs):
            x0, x1 = int(round(i * strip_w)), int(round((i + 1) * strip_w))
            canvas.paste(fit_cover(Image.open(p).convert("RGB"), x1 - x0, img_h), (x0, top))
        canvas.save(out, quality=93)
        return out

    # 顶部标题
    d = ImageDraw.Draw(canvas)
    title_h = int(H * IMG_TOP)
    fs = int(H * 0.075)
    while fs > 18:
        f = ImageFont.truetype(FONT_BOLD, fs)
        tw = d.textlength(title, font=f)
        if tw <= W * 0.90:
            break
        fs -= 2
    f = ImageFont.truetype(FONT_BOLD, fs)
    tw = d.textlength(title, font=f)
    ty = int(title_h / 2 - fs * 0.62)
    d.text(((W - tw) / 2, ty), title, font=f, fill=INK)

    # 六条竖图
    n = len(imgs)
    top = int(H * IMG_TOP)
    img_h = H - top
    strip_w = W / n
    for i, p in enumerate(imgs):
        x0 = int(round(i * strip_w))
        x1 = int(round((i + 1) * strip_w))
        tile = fit_cover(Image.open(p).convert("RGB"), x1 - x0, img_h)
        canvas.paste(tile, (x0, top))

    # 图上左下角地名
    if place:
        d2 = ImageDraw.Draw(canvas, "RGBA")
        fs2 = int(H * 0.042)
        f2 = ImageFont.truetype(FONT_BOLD, max(14, fs2))
        x = int(W * 0.025)
        y = H - int(H * 0.055) - fs2
        # 轻微阴影保证可读
        d2.text((x + 2, y + 2), place, font=f2, fill=(0, 0, 0, 90))
        d2.text((x, y), place, font=f2, fill=(255, 255, 255, 235))

    canvas.save(out, quality=93)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--title", required=True)
    ap.add_argument("--place", default="")
    ap.add_argument("--imgs", required=True, help="逗号分隔，6 张")
    ap.add_argument("--out", required=True)
    ap.add_argument("--size", default="1080x648")
    ap.add_argument("--no-text", action="store_true")
    a = ap.parse_args()
    imgs = [x.strip() for x in a.imgs.split(",") if x.strip()]
    W, H = [int(x) for x in a.size.lower().split("x")]
    print(build(a.title, a.place, imgs, a.out, (W, H), a.no_text))
