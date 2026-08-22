#!/usr/bin/env python3
"""给图片上下格配字(站酷快乐体,白色+浅橘粉描边+柔和阴影,每格顶部偏左)。
用法: python3 add_captions.py <图片> <输出> <上格文字> <下格文字> [字号比例]
默认字号比例 0.075(小一号)。
"""
import sys, os
from PIL import Image, ImageDraw, ImageFont

# 字体：优先用 skill data 目录下的 zk.woff2，找不到则回退用户目录
_HERE = os.path.dirname(os.path.abspath(__file__))
FONT_CANDIDATES = [
    os.path.join(_HERE, "..", "data", "zk.woff2"),
    os.path.expanduser("~/wanx-skill-data/zk.woff2"),
]
FONT = next((p for p in FONT_CANDIDATES if os.path.exists(p)), None)

if not FONT:
    os.makedirs(os.path.expanduser("~/wanx-skill-data"), exist_ok=True)
    FONT = os.path.expanduser("~/wanx-skill-data/zk.woff2")
    import urllib.request
    urllib.request.urlretrieve(
        "https://unpkg.com/@fontsource/zcool-kuaile@latest/files/zcool-kuaile-5-400-normal.woff2",
        FONT)

src, out, top_text, bottom_text = sys.argv[1:5]
fs_ratio = float(sys.argv[5]) if len(sys.argv) > 5 else 0.075

img = Image.open(src).convert("RGB")
W, H = img.size
draw = ImageDraw.Draw(img, "RGBA")

fs = int(W * fs_ratio)
font = ImageFont.truetype(FONT, fs)

stroke_w = max(1, int(fs * 0.04))
fill = (255, 255, 255, 255)          # 白色正文
stroke = (220, 150, 120, 255)        # 浅橘粉描边
sh = (255, 180, 150, 110)            # 柔和阴影
pad_left = int(W * 0.06)

for text, y_ratio in [(top_text, 0.05), (bottom_text, 0.56)]:
    y = int(H * y_ratio)
    draw.text((pad_left + stroke_w, y + stroke_w * 2), text, font=font, fill=sh)
    draw.text((pad_left, y), text, font=font, fill=fill, stroke_width=stroke_w, stroke_fill=stroke)

img.save(out)
print("SAVED", out, img.size)
