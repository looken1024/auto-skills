#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""抖音流量互助卡片流水线

子命令:
  fetch    <photo_id> [out.jpg]         Pexels CDN 抓 16:9 图 (1920x1080)
  search   <query> [--pp 5] [--out dir] 用 API 搜索图片并下载 16:9 图
  vsearch  <query> [--pp 5] [--res 720] [--out dir] 用 API 搜索视频并下载 mp4
  analyze  <ref_image> [boxes.json]     分析参考截图文字框位置(归一化坐标)
  render   <bg.jpg> <boxes.json>        叠字: 半透明黑底白字
           [--text "用|分隔"] [--size 44] [--alpha 115] [--random]
  variants <bg.jpg> <boxes.json>        去重变体: 镜像/裁切/滤镜/噪点/叠字
           [--outdir variants] [--count 4] [--random]
"""
import argparse, json, os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageEnhance

W, H = 1920, 1080
FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"

# 默认固定文案（4 条，对应 4 个固定位置）
DEFAULT_TEXTS = ["因为我一直刷新推荐页", "看完、点赞、评论+关注",
                 "然后你的作品就能被更多人看到", "众筹一万粉，永不取关"]

# 文案池：随机模式从这里抽 4 条（不重复）
TEXT_POOL = [
    "因为我一直刷新推荐页",
    "看完、点赞、评论+关注",
    "然后你的作品就能被更多人看到",
    "众筹一万粉，永不取关",
    "跟拍真的有流量",
    "想要流量就要多曝光自己",
    "加油，互动起来",
    "爆款音乐有流",
    "推荐页就是最大的流量池",
    "不说了我要去评论了",
    "你的作品总会被看到的",
    "扣1试试每天爆10000+",
]

# API key 从 skill 配置读取
CFG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config.json")
API_KEY = ""
try:
    API_KEY = json.load(open(CFG)).get("pexels_api_key", "")
except Exception:
    pass

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"}

def pick_texts(random_mode, n=4):
    """固定模式返回默认文案；随机模式从池子抽 n 条不重复"""
    if random_mode:
        return list(np.random.choice(TEXT_POOL, n, replace=False))
    return list(DEFAULT_TEXTS)

def fit_font(draw, text, cx, ww, base_size, min_size=26):
    """字号自适应：保证文字框不越过画面左右边界"""
    # 可用半宽 = 中心到最近边界的距离 - 边距
    half = int(min(cx, 1 - cx) * ww) - 50
    size = base_size
    while size > min_size:
        bb = draw.textbbox((0, 0), text, font=ImageFont.truetype(FONT, size))
        tw = bb[2] - bb[0]
        if tw / 2 + 40 <= half:
            return size
        size -= 2
    return min_size

def add_text(im, boxes, texts, size, alpha):
    draw = ImageDraw.Draw(im, "RGBA")
    ww, hh = im.size
    for text, b in zip(texts, boxes):
        fs = fit_font(draw, text, b["cx"], ww, size)
        font = ImageFont.truetype(FONT, fs)
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

def search(query, per_page, outdir):
    import urllib.request, urllib.parse
    if not API_KEY:
        print("ERROR: 缺少 API key，配置在 config.json 的 pexels_api_key")
        sys.exit(1)
    os.makedirs(outdir, exist_ok=True)
    url = "https://api.pexels.com/v1/search?query=%s&per_page=%d" % (
        urllib.parse.quote(query), per_page)
    req = urllib.request.Request(url, headers={"Authorization": API_KEY, **UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read())
    photos = data.get("photos", [])
    print(f"found {len(photos)} photos for '{query}'")
    saved = []
    for i, p in enumerate(photos, 1):
        pid = p["id"]
        if p["width"] < p["height"]:
            continue
        out = os.path.join(outdir, f"{query.replace(' ','_')}_{pid}.jpg")
        fetch(pid, out)
        saved.append(out)
    print(f"downloaded {len(saved)} landscape photos -> {outdir}")

def vsearch(query, per_page, res, outdir):
    import urllib.request, urllib.parse
    if not API_KEY:
        print("ERROR: 缺少 API key，配置在 config.json 的 pexels_api_key")
        sys.exit(1)
    os.makedirs(outdir, exist_ok=True)
    url = "https://api.pexels.com/videos/search?query=%s&per_page=%d" % (
        urllib.parse.quote(query), per_page)
    req = urllib.request.Request(url, headers={"Authorization": API_KEY, **UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read())
    videos = data.get("videos", [])
    print(f"found {len(videos)} videos for '{query}'")
    saved = []
    for v in videos:
        # 选分辨率接近目标且是横屏的版本（width>height 为横屏）
        best = None
        for f in v.get("video_files", []):
            if f.get("file_type") != "video/mp4" or not f.get("width"):
                continue
            if f["width"] < f["height"]:  # 只要横屏
                continue
            if best is None or abs(f["width"] - res) < abs(best["width"] - res):
                best = f
        if not best:
            continue
        link = best["link"]
        out = os.path.join(outdir, f"{query.replace(' ','_')}_{v['id']}_{best['width']}p.mp4")
        req = urllib.request.Request(link, headers=UA)
        with urllib.request.urlopen(req, timeout=120) as r:
            data = r.read()
        with open(out, "wb") as fh:
            fh.write(data)
        saved.append(out)
        print(f"saved {out} ({len(data)/1024/1024:.1f}MB)")
    print(f"downloaded {len(saved)} landscape videos -> {outdir}")

def fetch(photo_id, out):
    url = (f"https://images.pexels.com/photos/{photo_id}/pexels-photo-{photo_id}.jpeg"
           f"?auto=compress&cs=tinysrgb&w={W}&h={H}&fit=crop")
    import urllib.request
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read()
    im = Image.open(__import__("io").BytesIO(data)).convert("RGB")
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

def darken_top(im):
    grad = Image.new("L", im.size, 0)
    ww, hh = im.size
    for y in range(hh):
        grad.putpixel((0, y), int(255 * (1 - min(1, y/hh) * 0.30)))
    grad = grad.resize((ww, hh))
    return Image.composite(Image.new("RGB", im.size, (0,0,0)), im, grad)

def render(bg, boxes_json, texts, size, alpha, out):
    boxes = json.load(open(boxes_json))
    im = darken_top(Image.open(bg).convert("RGB"))
    im = add_text(im, boxes, texts, size, alpha)
    im.save(out, "JPEG", quality=92)
    print(f"saved {out}")

def variants(bg, boxes_json, texts, size, alpha, outdir, count):
    boxes = json.load(open(boxes_json))
    os.makedirs(outdir, exist_ok=True)
    np.random.seed(42)
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

# 内置参考布局（2026-08-29 从用户截图分析所得）
DEFAULT_BOXES = [
    {"cx": 0.195, "cy": 0.182, "w": 0.25, "h": 0.05},
    {"cx": 0.581, "cy": 0.388, "w": 0.30, "h": 0.05},
    {"cx": 0.509, "cy": 0.678, "w": 0.87, "h": 0.05},
    {"cx": 0.677, "cy": 0.917, "w": 0.36, "h": 0.05},
]

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("fetch"); p.add_argument("photo_id"); p.add_argument("out", nargs="?", default="pexels_16x9.jpg")
    p = sub.add_parser("search")
    p.add_argument("query"); p.add_argument("--pp", type=int, default=5); p.add_argument("--out", default="searched")
    p = sub.add_parser("vsearch")
    p.add_argument("query"); p.add_argument("--pp", type=int, default=5)
    p.add_argument("--res", type=int, default=720, help="目标宽度(px)，自动选最接近的横屏版本")
    p.add_argument("--out", default="videos")
    p = sub.add_parser("analyze"); p.add_argument("ref_image"); p.add_argument("out_json", nargs="?", default="boxes.json")
    p = sub.add_parser("render")
    p.add_argument("bg"); p.add_argument("boxes_json", nargs="?", default=None)
    p.add_argument("--out", default="card.jpg")
    p.add_argument("--text", default=None); p.add_argument("--size", type=int, default=44); p.add_argument("--alpha", type=int, default=115)
    p.add_argument("--random", action="store_true", help="从文案池随机抽 4 条")
    p = sub.add_parser("variants")
    p.add_argument("bg"); p.add_argument("boxes_json", nargs="?", default=None)
    p.add_argument("--outdir", default="variants")
    p.add_argument("--text", default=None); p.add_argument("--size", type=int, default=44); p.add_argument("--alpha", type=int, default=115)
    p.add_argument("--count", type=int, default=4); p.add_argument("--random", action="store_true")
    a = ap.parse_args()
    texts = None
    if hasattr(a, "text") and a.text:
        texts = a.text.split("|")
    if texts is None:
        texts = pick_texts(getattr(a, "random", False))
    boxes_json = getattr(a, "boxes_json", None) or None
    if boxes_json is None and os.path.exists("boxes.json"):
        boxes_json = "boxes.json"
    else:
        # 无 boxes 文件时用内置参考布局
        if boxes_json is None:
            boxes_json = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "default_boxes.json")
            if not os.path.exists(boxes_json):
                json.dump(DEFAULT_BOXES, open(boxes_json, "w"))
    if a.cmd == "fetch": fetch(a.photo_id, a.out)
    elif a.cmd == "search": search(a.query, a.pp, a.out)
    elif a.cmd == "vsearch": vsearch(a.query, a.pp, a.res, a.out)
    elif a.cmd == "analyze": analyze(a.ref_image, a.out_json)
    elif a.cmd == "render": render(a.bg, boxes_json, texts, a.size, a.alpha, a.out)
    elif a.cmd == "variants": variants(a.bg, boxes_json, texts, a.size, a.alpha, a.outdir, a.count)

if __name__ == "__main__":
    main()