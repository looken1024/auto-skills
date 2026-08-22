#!/usr/bin/env python3
"""
bar_chart_video.py - 动态条形图排行视频生成器
模板化:读 templates/*.json 模板 → 数据填充 → 逐帧 PIL 渲染 → ffmpeg 合成 MP4

依赖:python3 + Pillow + ffmpeg(无 matplotlib,轻量)
用法:
  # 完整生成
  python3 bar_chart_video.py <data.json> <template.json> <output.mp4> [--fps 30] [--duration-per-year 0.8]
  # 质检模式:只渲染首帧+尾帧 PNG,给模型检查越界,通过后再全量生成
  python3 bar_chart_video.py <data.json> <template.json> <output.mp4> --preview

数据格式 data.json:
{
  "title": "中美印法巴人口预测排行",
  "subtitle": "数据来源: FAO",
  "start_year": 2015,
  "end_year": 2025,
  "items": [
    {"name": "印度", "color": "#ff9933", "values": [1320000, ..., 1468632]},
    ...
  ]
}
"""
import argparse, json, math, os, subprocess, sys, tempfile
from PIL import Image, ImageDraw, ImageFont

# ---------- 模板默认值 ----------
DEFAULT_TEMPLATE = {
    "width": 1920, "height": 1080,      # 默认横版 16:9
    "bg_color": "#0a0c18",
    "title_color": "#ffffff", "title_size": 72,
    "subtitle_color": "#999999", "subtitle_size": 36,
    "bar_height": 80, "bar_gap": 32,
    "bar_radius": 12,
    "value_color": "#ffffff", "value_size": 48,
    "rank_font_size": 40,
    "year_color": "#ff5050", "year_size": 200,
    "year_position": [0.04, 0.06],     # 相对坐标 (x, y),横版年号放左上
    "bar_area_top": 0.32, "bar_area_bottom": 0.88,
    "label_font_size": 44,
    "fps": 30, "duration_per_year": 0.8,
    "max_value_scale": 1.12,
    # per_frame=条长相对当年最大值缩放(最大条满宽,条长严格跟数据比例变化)
    # global=相对所有年份最大值(条长全片统一比例,视觉更稳但变化幅度小)
    "value_scale_mode": "per_frame",
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
    d.rounded_rectangle([x, y, x+w, y+h], radius=radius, fill=color)

def is_landscape(cfg):
    return cfg["width"] >= cfg["height"]

def render_frame(cfg, font_path, year, values_by_year, output_path):
    """渲染单帧。values_by_year: [(name, color, value), ...] 已按当年值降序"""
    W, H = cfg["width"], cfg["height"]
    land = is_landscape(cfg)
    img = Image.new("RGB", (W, H), hex_to_rgb(cfg["bg_color"]))
    d = ImageDraw.Draw(img)

    # 标题/副标题
    f_title = load_font(font_path, cfg["title_size"])
    title_x = int(W * (0.05 if land else 0.06))
    title_y = int(H * (0.05 if not land else 0.06))
    d.text((title_x, title_y), cfg["title"], font=f_title, fill=hex_to_rgb(cfg["title_color"]))
    if cfg.get("subtitle"):
        f_sub = load_font(font_path, cfg["subtitle_size"])
        d.text((title_x, title_y + cfg["title_size"]*1.35), cfg["subtitle"],
               font=f_sub, fill=hex_to_rgb(cfg["subtitle_color"]))

    # 年份大字:横版放右上,竖版放左上
    f_year = load_font(font_path, cfg["year_size"])
    yx, yy = cfg["year_position"]
    if land:
        year_text = str(year)
        tw = d.textlength(year_text, font=f_year)
        d.text((W - tw - int(W*0.05), int(H*0.02)), year_text, font=f_year, fill=hex_to_rgb(cfg["year_color"]))
    else:
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

    # 缩放基准:main 里每帧设置 _scale_max(per_frame 模式下跟随当年最大)
    scale_max = cfg.get("_scale_max", 1)
    # 横版标签区窄(左 0.16 起条),竖版宽(左 0.28 起条)
    bar_left = int(W * (0.16 if land else 0.28))
    bar_right = int(W * (0.80 if land else 0.90))
    bar_max_w = bar_right - bar_left
    f_label = load_font(font_path, cfg["label_font_size"])
    f_value = load_font(font_path, cfg["value_size"])
    f_rank = load_font(font_path, cfg["rank_font_size"])

    rank_x = int(W * (0.03 if land else 0.05))
    label_x = int(W * (0.09 if land else 0.13))
    for i, (name, color, value) in enumerate(values_by_year):
        y = start_y + i*(bar_h + gap)
        if cfg["show_rank"]:
            d.text((rank_x, y + bar_h//2 - cfg["rank_font_size"]//2), str(i+1),
                   font=f_rank, fill=hex_to_rgb("#666666"))
        d.text((label_x, y + bar_h//2 - cfg["label_font_size"]//2), name,
               font=f_label, fill=hex_to_rgb("#dddddd"))
        bw = max(8, int(bar_max_w * value / scale_max))
        draw_rounded_bar(d, bar_left, y, bw, bar_h, hex_to_rgb(color), cfg["bar_radius"])
        if cfg["show_value"]:
            num_text = f"{value:,.0f}"
            d.text((bar_left + bw + 12, y + bar_h//2 - cfg["value_size"]//2), num_text,
                   font=f_value, fill=hex_to_rgb(cfg["value_color"]))

    img.save(output_path)

def sorted_vals(items, year_idx):
    return sorted([(it["name"], it["color"], it["vals"][year_idx]) for it in items], key=lambda x: -x[2])

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
    ap.add_argument("--end-pause", type=float, default=None, help="结尾暂停秒数(保持终帧画面,默认0)")
    ap.add_argument("--preview", action="store_true",
                    help="质检模式:只渲染首帧+尾帧PNG(不生成视频),供模型检查文字越界")
    args = ap.parse_args()

    data = json.load(open(args.data, encoding="utf-8"))
    tpl = json.load(open(args.template, encoding="utf-8"))
    cfg = {**DEFAULT_TEMPLATE, **tpl}
    # 数据文件提供标题/副标题(模板只管样式)
    cfg["title"] = data.get("title", "")
    cfg["subtitle"] = data.get("subtitle", "")
    if args.fps: cfg["fps"] = args.fps
    if args.duration_per_year: cfg["duration_per_year"] = args.duration_per_year
    if args.width: cfg["width"] = args.width
    if args.height: cfg["height"] = args.height
    if args.end_pause is not None:
        cfg["end_pause"] = args.end_pause
    elif "end_pause" not in cfg:
        cfg["end_pause"] = 0

    years = list(range(data["start_year"], data["end_year"] + 1))
    items = []
    global_max = 0
    for it in data["items"]:
        vals = it["values"]
        assert len(vals) == len(years), f"{it['name']} 数值数量({len(vals)})≠年份数({len(years)})"
        global_max = max(global_max, max(vals))
        items.append({"name": it["name"], "color": it.get("color", "#4a90d9"), "vals": vals})
    cfg["_global_max"] = global_max

    font_path = find_font()

    # ---- preview 质检模式:只渲染首帧+尾帧 ----
    if args.preview:
        outdir = os.path.dirname(os.path.abspath(args.output))
        base = os.path.splitext(os.path.basename(args.output))[0]
        # 首帧
        first = sorted_vals(items, 0)
        cfg["_scale_max"] = max(v for _,_,v in first) * cfg["max_value_scale"]
        p1 = os.path.join(outdir, f"{base}_start.png")
        render_frame(cfg, font_path, years[0], first, p1)
        # 尾帧
        last = sorted_vals(items, len(years)-1)
        cfg["_scale_max"] = max(v for _,_,v in last) * cfg["max_value_scale"]
        p2 = os.path.join(outdir, f"{base}_end.png")
        render_frame(cfg, font_path, years[-1], last, p2)
        print(f"预览帧已生成:\n  {p1}\n  {p2}")
        print("请用视觉模型检查:文字是否越界/重叠、条形是否超界。确认后去掉 --preview 全量生成。")
        return

    # ---- 全量渲染 ----
    frame_dir = tempfile.mkdtemp(prefix="bcv_")
    total = int(len(years)*cfg["fps"]*cfg["duration_per_year"])
    print(f"渲染 {len(years)} 年 * {cfg['fps']}fps * {cfg['duration_per_year']}s = {total} 帧")

    frame_no = 0
    last_frame_all = {}   # name -> 上一帧插值(全量,支持国家进出榜平滑)
    top_n = cfg.get("top_n", None)
    for yi, year in enumerate(years):
        cur_all = [(it["name"], it["color"], it["vals"][yi]) for it in items]
        steps = int(cfg["fps"] * cfg["duration_per_year"])
        for s in range(steps):
            if yi == 0:
                t = 1.0   # 首年直接到位
            else:
                t = s / steps
            interp_all = []
            for name, color, v in cur_all:
                if yi == 0:
                    iv = v
                else:
                    pv = last_frame_all.get(name, 0.0)
                    iv = pv + (v - pv) * t
                interp_all.append((name, color, iv))
            interp_all.sort(key=lambda x: -x[2])
            frame_vals = interp_all[:top_n] if top_n else interp_all
            # per_frame:每帧相对当年最大缩放 → 条长严格随数据比例变化(最大条每次满宽)
            # global:固定全周期最大 → 条长绝对比例(变化幅度小但视觉稳定)
            if cfg["value_scale_mode"] == "per_frame":
                cfg["_scale_max"] = max(v for _,_,v in frame_vals) * cfg["max_value_scale"]
            else:
                cfg["_scale_max"] = cfg["_global_max"] * cfg["max_value_scale"]
            out = os.path.join(frame_dir, f"f{frame_no:06d}.png")
            render_frame(cfg, font_path, year, frame_vals, out)
            frame_no += 1
            last_frame_all = {name: iv for name, _, iv in interp_all}

    # ---- 结尾暂停:复制终帧画面 N 秒(不插值) ----
    pause_frames = int(cfg.get("end_pause", 0) * cfg["fps"])
    if pause_frames > 0 and frame_no > 0:
        import shutil
        last_frame = os.path.join(frame_dir, f"f{frame_no-1:06d}.png")
        for k in range(pause_frames):
            shutil.copy(last_frame, os.path.join(frame_dir, f"f{frame_no:06d}.png"))
            frame_no += 1
        print(f"结尾暂停 {cfg['end_pause']}s (+{pause_frames} 帧)")

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