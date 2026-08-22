#!/usr/bin/env python3
"""
bar_chart_video.py - 动态条形图排行视频生成器
模板化:读 templates/*.json 模板 → 数据填充 → 逐帧 PIL 渲染 → ffmpeg 合成 MP4

依赖:python3 + Pillow + ffmpeg(无 matplotlib,轻量)
用法:
  python3 bar_chart_video.py <data.json> <template.json> <output.mp4> [--fps 30] [--duration-per-year 1.0]
数据格式 data.json:
{
  "title": "中美印法巴人口预测排行",
  "subtitle": "数据来源: FAO",
  "unit": "千人",
  "start_year": 2015,
  "end_year": 2025,
  "items": [  // 每个国家一条, values 按年份顺序
    {"name": "印度", "color": "#ff9933", "values": [1320000, ..., 1468632]},
    ...
  ]
}
"""
import argparse, json, math, os, subprocess, sys, tempfile
from PIL import Image, ImageDraw, ImageFont

# ---------- 模板默认值 ----------
DEFAULT_TEMPLATE = {
    "width": 1080, "height": 1920,
    "bg_color": "#0a0c18",
    "title_color": "#ffffff", "title_size": 64,
    "subtitle_color": "#999999", "subtitle_size": 36,
    "bar_height": 72, "bar_gap": 28,
    "bar_radius": 12,
    "value_color": "#ffffff", "value_size": 52,
    "rank_font_size": 44,
    "year_color": "#ff5050", "year_size": 200,
    "year_position": [0.07, 0.13],  # 相对坐标 (x, y)
    "bar_area_top": 0.30, "bar_area_bottom": 0.90,
    "label_font_size": 48,
    "fps": 30, "duration_per_year": 0.8,
    "max_value_scale": 1.15,
    "show_rank": True,
    "show_value": True,
}

FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "C:/Windows/Fonts/msyh.ttc",
]

def find_font():
    for p in FONT_CANDIDATES:
        if os.path.exists(p):
            return p
    raise FileNotFoundError("未找到中文字体,请安装 Noto CJK")

def hex_to_rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def load_font(path, size):
    return ImageFont.truetype(path, size)

def draw_rounded_bar(d, x, y, w, h, color, radius):
    """画圆角条形"""
    d.rounded_rectangle([x, y, x+w, y+h], radius=radius, fill=color)

def render_frame(cfg, font_path, year_idx, year, values_by_year, output_path):
    """渲染单帧。values_by_year: [(name, color, value), ...] 已按当年值降序"""
    W, H = cfg["width"], cfg["height"]
    img = Image.new("RGB", (W, H), hex_to_rgb(cfg["bg_color"]))
    d = ImageDraw.Draw(img)

    # 标题
    f_title = load_font(font_path, cfg["title_size"])
    d.text((W*0.06, H*0.05), cfg["title"], font=f_title, fill=hex_to_rgb(cfg["title_color"]))
    # 副标题
    if cfg.get("subtitle"):
        f_sub = load_font(font_path, cfg["subtitle_size"])
        d.text((W*0.06, H*0.05 + cfg["title_size"]*1.35), cfg["subtitle"], font=f_sub, fill=hex_to_rgb(cfg["subtitle_color"]))

    # 年份(大号)
    f_year = load_font(font_path, cfg["year_size"])
    yx, yy = cfg["year_position"]
    d.text((W*yx, H*yy), str(year), font=f_year, fill=hex_to_rgb(cfg["year_color"]))

    # 条形区几何
    bar_h = cfg["bar_height"]
    gap = cfg["bar_gap"]
    n = len(values_by_year)
    top = int(H * cfg["bar_area_top"])
    bottom = int(H * cfg["bar_area_bottom"])
    usable = bottom - top
    total_h = n*bar_h + (n-1)*gap
    start_y = top + max(0, (usable - total_h) // 2)

    # 最大值(取所有年份最大,保证比例稳定)
    all_max = cfg.get("_global_max", 1)
    scale_max = all_max * cfg["max_value_scale"]
    bar_left = int(W * 0.28)          # 标签区
    bar_right = int(W * 0.90)         # 条形终点
    bar_max_w = bar_right - bar_left
    f_label = load_font(font_path, cfg["label_font_size"])
    f_value = load_font(font_path, cfg["value_size"])
    f_rank = load_font(font_path, cfg["rank_font_size"])

    for i, (name, color, value) in enumerate(values_by_year):
        y = start_y + i*(bar_h + gap)
        # 排名数字
        if cfg["show_rank"]:
            d.text((int(W*0.05), y + bar_h//2 - cfg["rank_font_size"]//2), str(i+1),
                   font=f_rank, fill=hex_to_rgb("#666666"))
        # 国家名
        d.text((int(W*0.13), y + bar_h//2 - cfg["label_font_size"]//2), name,
               font=f_label, fill=hex_to_rgb("#dddddd"))
        # 条形
        bw = max(8, int(bar_max_w * value / scale_max))
        draw_rounded_bar(d, bar_left, y, bw, bar_h, hex_to_rgb(color), cfg["bar_radius"])
        # 数值(条尾右侧)
        if cfg["show_value"]:
            num_text = f"{value:,.0f}"
            tw = d.textlength(num_text, font=f_value)
            d.text((bar_left + bw + 12, y + bar_h//2 - cfg["value_size"]//2), num_text,
                   font=f_value, fill=hex_to_rgb(cfg["value_color"]))

    img.save(output_path)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    ap.add_argument("template")
    ap.add_argument("output")
    ap.add_argument("--fps", type=int, default=None)
    ap.add_argument("--duration-per-year", type=float, default=None)
    ap.add_argument("--width", type=int, default=None)
    ap.add_argument("--height", type=int, default=None)
    ap.add_argument("--keep-frames", action="store_true", help="保留中间帧目录")
    args = ap.parse_args()

    data = json.load(open(args.data, encoding="utf-8"))
    tpl = json.load(open(args.template, encoding="utf-8"))
    cfg = {**DEFAULT_TEMPLATE, **tpl}
    if args.fps: cfg["fps"] = args.fps
    if args.duration_per_year: cfg["duration_per_year"] = args.duration_per_year
    if args.width: cfg["width"] = args.width
    if args.height: cfg["height"] = args.height

    # 年份轴
    years = list(range(data["start_year"], data["end_year"] + 1))
    # 预处理 items -> {name: {color, vals}}
    items = []
    global_max = 0
    for it in data["items"]:
        vals = it["values"]
        assert len(vals) == len(years), f"{it['name']} 数值数量({len(vals)})≠年份数({len(years)})"
        global_max = max(global_max, max(vals))
        items.append({"name": it["name"], "color": it.get("color", "#4a90d9"), "vals": vals})
    cfg["_global_max"] = global_max

    font_path = find_font()
    frame_dir = tempfile.mkdtemp(prefix="bcv_")
    print(f"渲染 {len(years)} 年 * {cfg['fps']}fps * {cfg['duration_per_year']}s = {int(len(years)*cfg['fps']*cfg['duration_per_year'])} 帧")

    frame_no = 0
    for yi, year in enumerate(years):
        # 当年所有条目值
        cur = [(it["name"], it["color"], it["vals"][yi]) for it in items]
        cur.sort(key=lambda x: -x[2])
        steps = int(cfg["fps"] * cfg["duration_per_year"])
        for s in range(steps):
            # 插值:上一帧值 -> 当年值(首年直接到位)
            if yi == 0:
                frame_vals = cur
            else:
                prev = [(it["name"], it["color"], it["vals"][yi-1]) for it in items]
                prev_map = {p[0]: p for p in prev}
                frame_vals = []
                for name, color, v in cur:
                    pv = prev_map[name][2]
                    interp = pv + (v - pv) * (s / steps)
                    frame_vals.append((name, color, interp))
                frame_vals.sort(key=lambda x: -x[2])
            out = os.path.join(frame_dir, f"f{frame_no:06d}.png")
            render_frame(cfg, font_path, yi, year, frame_vals, out)
            frame_no += 1

    # ffmpeg 合成
    fps = cfg["fps"]
    cmd = ["ffmpeg", "-y", "-framerate", str(fps),
           "-i", os.path.join(frame_dir, "f%06d.png"),
           "-c:v", "libx264", "-pix_fmt", "yuv420p",
           "-crf", "20", "-preset", "medium",
           args.output]
    print("ffmpeg 合成中...")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-2000:], file=sys.stderr)
        sys.exit(1)
    print(f"✅ 完成: {args.output} ({os.path.getsize(args.output)//1024} KB)")
    if not args.keep_frames:
        import shutil; shutil.rmtree(frame_dir, ignore_errors=True)

if __name__ == "__main__":
    main()