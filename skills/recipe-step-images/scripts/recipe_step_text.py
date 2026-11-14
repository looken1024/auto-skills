#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给菜谱步骤图统一加文字（样式、位置完全一致）。

用法:
  python3 recipe_step_text.py --img 1.jpg --text "菜花掰成小朵..." --out out/1.jpg --style A
  python3 recipe_step_text.py --batch steps.json --outdir out --style A

steps.json 格式:
  [{"img": "1.jpg", "text": "处理菜花：菜花掰成小朵...", "step": 1}, ...]

样式:
  A = 顶部半透明黑底 + 白字（默认，最稳）
  B = 白字 + 黑描边，无底色（浅色底图慎用）
"""
import argparse, json, os, sys
from PIL import Image, ImageDraw, ImageFont

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _find_font():
    cands = [
        os.path.join(SKILL_DIR, "assets/fonts/noto-serif-sc-chinese-simplified-700-normal.woff2"),
        os.path.expanduser("~/recipe_imgs/fonts/noto-serif-sc-chinese-simplified-700-normal.woff2"),
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    ]
    for p in cands:
        if os.path.exists(p):
            return p
    return cands[-1]

FONT_PATH = _find_font()
WIDTH = 1080            # 统一输出宽度，位置比例才完全一致
MARGIN_X = 0.070        # 文字区左右边距（相对宽度）
TOP = 0.045             # 文字区距顶边（相对高度）
FONT_RATIO = 0.042      # 字号 / 图片宽度
LINE_SPACING = 1.45
BOX_ALPHA = 150         # 样式 A 黑底透明度
RADIUS_RATIO = 0.012


def wrap_cjk(draw, text, font, max_w):
    """按像素宽度折行；中文逐字断，英文数字尽量不切断。"""
    lines, cur = [], ""
    for ch in text:
        if ch == "\n":
            lines.append(cur); cur = ""; continue
        trial = cur + ch
        if draw.textlength(trial, font=font) <= max_w:
            cur = trial
        else:
            lines.append(cur); cur = ch
    if cur:
        lines.append(cur)
    return lines


def fit_font(draw, text, max_w, max_h, base_size):
    """从基准字号往下缩，直到文字块能放进给定区域。"""
    size = base_size
    while size >= 18:
        font = ImageFont.truetype(FONT_PATH, size)
        lines = wrap_cjk(draw, text, font, max_w)
        lh = int(size * LINE_SPACING)
        if lh * len(lines) <= max_h:
            return font, lines, lh
        size -= 2
    font = ImageFont.truetype(FONT_PATH, 18)
    return font, wrap_cjk(draw, text, font, max_w), int(18 * LINE_SPACING)


def render(img_path, text, out_path, style="A"):
    im = Image.open(img_path).convert("RGB")
    w, h = im.size
    if w != WIDTH:
        im = im.resize((WIDTH, int(h * WIDTH / w)), Image.LANCZOS)
    w, h = im.size

    draw = ImageDraw.Draw(im, "RGBA")
    max_w = int(w * (1 - 2 * MARGIN_X))
    max_h = int(h * 0.32)          # 最多占 32% 高度
    font, lines, lh = fit_font(draw, text, max_w, max_h, int(w * FONT_RATIO))

    block_h = lh * len(lines)
    top_y = int(h * TOP)           # 文字统一在图片上方

    if style == "A":
        pad_x, pad_y = int(w * 0.018), int(h * 0.014)
        box = [int(w * MARGIN_X) - pad_x, top_y - pad_y,
               int(w * MARGIN_X) + max_w + pad_x, top_y + block_h + pad_y]
        draw.rounded_rectangle(box, radius=int(w * RADIUS_RATIO), fill=(0, 0, 0, BOX_ALPHA))

    y = top_y
    for line in lines:
        if style == "A":
            draw.text((int(w * MARGIN_X), y), line, font=font, fill=(255, 255, 255, 255))
        else:
            draw.text((int(w * MARGIN_X), y), line, font=font, fill=(255, 255, 255, 255),
                      stroke_width=max(2, int(w * 0.0022)), stroke_fill=(0, 0, 0, 235))
        y += lh

    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    im.save(out_path, quality=92)
    return out_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--img"); ap.add_argument("--text"); ap.add_argument("--out")
    ap.add_argument("--batch", help="JSON 文件: [{img,text,step}]")
    ap.add_argument("--outdir", default="out")
    ap.add_argument("--style", choices=["A", "B"], default="A")
    a = ap.parse_args()

    if a.batch:
        items = json.load(open(a.batch, encoding="utf-8"))
        for it in items:
            out = os.path.join(a.outdir, os.path.basename(it["img"]))
            print(render(it["img"], it["text"], out, a.style))
        return
    if not (a.img and a.text and a.out):
        sys.exit("需要 --img/--text/--out，或用 --batch")
    print(render(a.img, a.text, a.out, a.style))


if __name__ == "__main__":
    main()
