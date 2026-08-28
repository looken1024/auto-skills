#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""抖音流量互助卡片流水线

子命令:
  fetch    <photo_id> [out.jpg]         Pexels CDN 抓 16:9 图 (1920x1080)
  analyze  <ref_image> [boxes.json]     分析参考截图文字框位置(归一化坐标)
  render   <bg.jpg> <boxes.json>        叠字: 半透明黑底白字
           [--text "用|分隔"] [--size 44] [--alpha 115]
  variants <bg.jpg> <boxes.json>        去重变体: 镜像/裁切/滤镜/噪点/叠字
           [--outdir variants] [--count 4]
"""
import argparse, json, os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageEnhance

W, H = 1920, 1080
FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
DEFAULT_TEXTS = ["因为我一直刷新推荐页", "看完、点赞、评论+关注",
                 "然后你的作品就能被更多人看到", "众筹一万粉，永不取关"]

def fetch(photo_id, out):
    url = (f"https://images.pexels.com/photos/{photo_id}/pexels-photo-{photo_id}.jpeg"
           f"?auto=compress&cs=tinysrgb&w={W}&h={H}&fit=crop")
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read()
    im = Image.open(io := __import__("io").BytesIO(data)).convert("RGB")
    im.save(out, "JPEG", quality=92)
    print(f"saved {out} {im.size}")

def analyze(ref_image, out_json):
    a = np.array(Image.open(ref_image).convert("RGB")).astype(float)
    hh, ww = a.shape[:2]
    R, G, B = a[:,:,0], a[:,:,1], a[:,:,2]
    gray = a.mean(axis=2)
    neutral = (abs(R-G) < 18) & (abs(G-B) < 18) & (gray < 130)
    row_n = neutral.mean(axis=1)
    segs, in_seg = [], False
    start = 0
    for y in range(hh):
        if row_n[y] > 0.03 and not in_seg:
            in_seg, start = True, y
        elif row_n[y] <= 0.03 and in_seg:
            in_seg = False
            if y - start > 5: segs.append([start, y])
    if in_seg and hh-1-start > 5: segs.append([start, hh-1])
    merged = []
    for s in segs:
        if merged and s[0] - merged[-1][1] < 12:
            merged[-1][1] = s[1]
        else:
            merged.append(list(s))
    boxes = []
    for y0, y1 in merged:
        col_n = neutral[y0:y1].mean(axis=0)
        k = np.ones(5)/5
        cs = np.convolve(np.pad(col_n, 2, mode="edge"), k, mode="same")
        cols = np.where(cs > 0.15)[0]
        if not len(cols): continue
        x0, x1 = max(0, cols[0]-8), min(ww-1, cols[-1]+8)
        y0p, y1p = max(0, y0-6), min(hh-1, y1+6)
        boxes.append({"cx": (x0+x1)/2/ww, "cy": (y0p+y1p)/2/hh,
                      "w": (x1-x0)/ww, "h": (y1p-y0p)/hh})
    json.dump(boxes, open(out_json, "w"), indent=1, ensure_ascii=False)
    print(f"analyzed {len(boxes)} boxes -> {out_json}")

def add_text(im, boxes, texts, size, alpha):
    draw = ImageDraw.Draw(im, "RGBA")
    font = ImageFont.truetype(FONT, size)
    ww, hh = im.size
    for text, b in zip(texts, boxes):
        bb = draw.textbbox((0, 0), text, font=font)
        tw, th = bb[2]-bb[0], bb[3]-bb[1]
        pad_x, pad_y = 40, 24
        bw, bh = tw + pad_x*2, th + pad_y*2
        x0 = int(b["cx"]*ww - bw/2); y0 = int(b["cy"]*hh - bh/2)
        x0 = max(10, min(ww-bw-10, x0)); y0 = max(10, min(hh-bh-10, y0))
        draw.rounded_rectangle([x0, y0, x0+bw, y0+bh], radius=bh//2,
                               fill=(0, 0, 0, alpha))
        draw.text((x0+pad_x-bb[0], y0+pad_y-bb[1]), text, font=font,
                  fill=(255, 255, 255, 255))
    return im

def render(bg, boxes_json, texts, size, alpha, out):
    boxes = json.load(open(boxes_json))
    im = Image.open(bg).convert("RGB")
    # 顶部轻微压暗保证白字清晰
    grad = Image.new("L", im.size, 0)
    ww, hh = im.size
    for y in range(hh):
        grad.putpixel((0, y), int(255 * (1 - min(1, y/hh) * 0.30)))
    grad = grad.resize((ww, hh))
    im = Image.composite(Image.new("RGB", im.size, (0,0,0)), im, grad)
    im = add_text(im, boxes, texts, size, alpha)
    im.save(out, "JPEG", quality=92)
    print(f"saved {out}")

def variants(bg, boxes_json, texts, size, alpha, outdir, count):
    boxes = json.load(open(boxes_json))
    os.makedirs(outdir, exist_ok=True)
    np.random.seed(42)
    # 配方: (flip, contrast, color, brightness, noise, hue)
    recipes = [
        (True,  1.05, 1.08, 1.02, 2.5, None),
        (True,  1.10, 0.92, 1.00, 3.0, None),
        (True,  1.00, 1.00, 1.02, 2.5, 8),
        (False, 1.04, 1.06, 1.03, 2.0, None),
        (True,  1.08, 1.05, 1.05, 3.5, -6),
        (False, 1.12, 0.90, 0.97, 3.0, None),
    ][:count]
    base = Image.open(bg).convert("RGB")
    for i, (flip, cont, col, bri, noise, hue) in enumerate(recipes, 1):
        im = base.copy()
        if flip: im = im.transpose(Image.FLIP_LEFT_RIGHT)
        # 微裁切缩放
        ww, hh = im.size
        cw, ch = int(ww*0.02), int(hh*0.02)
        im = im.crop((cw, ch, ww-cw, hh-ch)).resize((ww, hh), Image.LANCZOS)
        im = ImageEnhance.Contrast(im).enhance(cont)
        im = ImageEnhance.Color(im).enhance(col)
        im = ImageEnhance.Brightness(im).enhance(bri)
        if hue:
            hsv = im.convert("HSV")
            h_, s_, v_ = hsv.split()
            ha = (np.array(h_).astype(int) + hue).clip(0, 255).astype(np.uint8)
            im = Image.merge("HSV", (Image.fromarray(ha), s_, v_)).convert("RGB")
        arr = np.array(im).astype(float)
        arr = np.clip(arr + np.random.normal(0, noise, arr.shape), 0, 255).astype(np.uint8)
        im = Image.fromarray(arr)
        im = add_text(im, boxes, texts, size, alpha)
        out = os.path.join(outdir, f"v{i}.jpg")
        im.save(out, "JPEG", quality=88)
        print(f"saved {out}")

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("fetch"); p.add_argument("photo_id"); p.add_argument("out", nargs="?", default="pexels_16x9.jpg")
    p = sub.add_parser("analyze"); p.add_argument("ref_image"); p.add_argument("out_json", nargs="?", default="boxes.json")
    p = sub.add_parser("render")
    p.add_argument("bg"); p.add_argument("boxes_json"); p.add_argument("--out", default="card.jpg")
    p.add_argument("--text", default=None); p.add_argument("--size", type=int, default=44); p.add_argument("--alpha", type=int, default=115)
    p = sub.add_parser("variants")
    p.add_argument("bg"); p.add_argument("boxes_json"); p.add_argument("--outdir", default="variants")
    p.add_argument("--text", default=None); p.add_argument("--size", type=int, default=44); p.add_argument("--alpha", type=int, default=115)
    p.add_argument("--count", type=int, default=4)
    a = ap.parse_args()
    texts = DEFAULT_TEXTS if not a.text else a.text.split("|")
    if a.cmd == "fetch": fetch(a.photo_id, a.out)
    elif a.cmd == "analyze": analyze(a.ref_image, a.out_json)
    elif a.cmd == "render": render(a.bg, a.boxes_json, texts, a.size, a.alpha, a.out)
    elif a.cmd == "variants": variants(a.bg, a.boxes_json, texts, a.size, a.alpha, a.outdir, a.count)

if __name__ == "__main__":
    main()
