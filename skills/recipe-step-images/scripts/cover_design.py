#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""菜谱封面排版：底图 + 顶部渐变 + 中文主标题/英文副标题/标签。

用法:
  python3 cover_design.py --img cover_raw.jpg --title 干锅菜花 \
      --en "DRY POT CAULIFLOWER" --kicker "家常川味 · 2～3人份" --out cover.jpg
"""
import argparse, os
from PIL import Image, ImageDraw, ImageFont

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _font(name, fallback):
    cands = [
        os.path.join(SKILL_DIR, "assets/fonts", name),
        os.path.expanduser("~/recipe_imgs/fonts/" + name),
        fallback,
    ]
    for p in cands:
        if os.path.exists(p):
            return p
    return cands[-1]

SERIF = _font("noto-serif-sc-chinese-simplified-700-normal.woff2",
              "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc")
LATIN = _font("noto-serif-sc-latin-700-normal.woff2", SERIF)
W, H = 1080, 1440
MARGIN = 78
ACCENT = (198, 62, 40)        # 干辣椒红
CREAM = (245, 236, 224)


def cover_fill(img):
    """等比放大并居中裁剪，填满 1080x1440。"""
    iw, ih = img.size
    scale = max(W / iw, H / ih)
    img = img.resize((int(iw * scale + 0.5), int(ih * scale + 0.5)), Image.LANCZOS)
    x = (img.width - W) // 2
    y = (img.height - H) // 2
    return img.crop((x, y, x + W, y + H))


def gradient_top(h_ratio=0.46, max_alpha=215):
    """顶部向下渐隐的黑色遮罩。"""
    gh = int(H * h_ratio)
    mask = Image.new("L", (1, gh))
    px = mask.load()
    for y in range(gh):
        t = y / max(1, gh - 1)
        px[0, y] = int(max_alpha * (1 - t) ** 1.6)
    return mask.resize((W, gh))


def draw_spaced(draw, xy, text, font, fill, spacing=0, shadow=False):
    """逐字绘制，制造字距；返回总宽度。"""
    x, y = xy
    if shadow:
        sx, sy = x + 2, y + 4
        for ch in text:
            if ch.strip():
                draw.text((sx, sy), ch, font=font, fill=(0, 0, 0, 110))
            sx += draw.textlength(ch, font=font) + spacing
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill)
        x += draw.textlength(ch, font=font) + spacing
    return x - spacing - xy[0]


def build(img_path, title, en, kicker, out, accent_text=""):
    base = cover_fill(Image.open(img_path).convert("RGB"))
    canvas = base.convert("RGBA")
    gh = int(H * 0.46)
    shade = Image.new("RGBA", (W, gh), (8, 6, 4, 255))
    shade.putalpha(gradient_top())
    canvas.alpha_composite(shade, (0, 0))

    d = ImageDraw.Draw(canvas)
    f_kicker = ImageFont.truetype(SERIF, 27)
    f_title = ImageFont.truetype(SERIF, 172)
    f_en = ImageFont.truetype(LATIN, 24)

    y = 108
    draw_spaced(d, (MARGIN, y), kicker, f_kicker, CREAM + (205,), spacing=4)
    y += 74
    draw_spaced(d, (MARGIN - 4, y), title, f_title, (255, 255, 255, 255),
                spacing=14, shadow=True)
    y += 232
    d.rectangle([MARGIN, y, MARGIN + 96, y + 7], fill=ACCENT + (255,))
    y += 30
    draw_spaced(d, (MARGIN, y), en, f_en, CREAM + (170,), spacing=11)

    if accent_text:
        f_small = ImageFont.truetype(SERIF, 26)
        d.text((MARGIN, H - 92), accent_text, font=f_small, fill=CREAM + (190,))

    canvas.convert("RGB").save(out, quality=93)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--img", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--en", default="")
    ap.add_argument("--kicker", default="")
    ap.add_argument("--accent-text", default="")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    print(build(a.img, a.title, a.en, a.kicker, a.out, a.accent_text))
