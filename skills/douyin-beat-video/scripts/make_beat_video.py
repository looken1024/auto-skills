#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""卡点视频合成器: 按节拍点切换素材, 支持入场缩放动画
用法:
  python3 make_beat_video.py --beats beats.json --mats <素材目录> --music <原视频> --out out.mp4 [--anim zoom-in|none]
"""
import subprocess, os, sys, json, glob, argparse


def ffprobe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                        "-show_entries", "stream=width,height,duration",
                        "-of", "csv=p=0", path], capture_output=True, text=True)
    vals = r.stdout.strip().split(",")
    try:
        return [float(x) for x in vals if x]
    except ValueError:
        return []


def main():
    ap = argparse.ArgumentParser(description="卡点视频合成器")
    ap.add_argument("--beats", required=True, help="beats.json (beat_detect.py 输出)")
    ap.add_argument("--mats", required=True, help="素材视频目录")
    ap.add_argument("--music", required=True, help="原视频或音频文件(取音轨)")
    ap.add_argument("--out", default="beat_video.mp4")
    ap.add_argument("--anim", choices=["zoom-in", "none"], default="zoom-in",
                    help="入场动画: zoom-in=放大收缩(默认), none=无")
    ap.add_argument("--res", default="1280x720", help="输出分辨率 WxH")
    ap.add_argument("--min-seg", type=float, default=0.4,
                    help="短于此秒数的段丢弃或并入前一段(防闪切)")
    ap.add_argument("--start-offset", type=float, default=0.5,
                    help="每段从素材的该秒数开始截取(避开开头黑帧)")
    ap.add_argument("--reuse-offset", type=float, default=3.0,
                    help="素材不足时复用的时间偏移步长(秒)")
    ap.add_argument("--keep-work", action="store_true", help="保留中间片段文件")
    args = ap.parse_args()

    beats_data = json.load(open(args.beats))
    beats = beats_data["beats"]
    music_end = beats_data.get("duration", beats[-1] + 1.0)
    print(f"节拍 {len(beats)} 个, 音乐 {music_end:.2f}s, BPM={beats_data.get('bpm')}")

    W, H = [int(x) for x in args.res.lower().split("x")]
    BW, BH = int(W * 1.25), int(H * 1.25)  # zoompan 工作区(1.4x 放大有富余)
    edges = [0.0] + beats
    segs = [(edges[i], edges[i+1]-edges[i]) for i in range(len(edges)-1)]
    segs.append((edges[-1], music_end - edges[-1]))
    # 合并保护: 过短段(前奏弱拍)丢弃首段, 其余并入前一段
    merged = []
    for st, dur in segs:
        if dur < args.min_seg:
            if not merged:
                continue
            prev_st, prev_dur = merged[-1]
            merged[-1] = (prev_st, prev_dur + dur)
        else:
            merged.append((st, dur))
    segs = merged

    mats = sorted(glob.glob(os.path.join(args.mats, "*.mp4")))
    landscape = []
    for m in mats:
        info = ffprobe(m)
        if len(info) >= 3 and info[0] >= info[1]:
            landscape.append((m, info[0], info[1], info[2]))
    if not landscape:
        print("ERROR: 没有可用横屏素材"); sys.exit(1)
    print(f"横屏素材 {len(landscape)} 个, 段数 {len(segs)}")

    mat_for_seg = [landscape[i] if i < len(landscape) else landscape[i % len(landscape)]
                   for i in range(len(segs))]
    use_count = {}
    out_dir = os.path.dirname(os.path.abspath(args.out)) or "."
    os.makedirs(out_dir, exist_ok=True)
    concat_list, work_files = [], []

    anim_vf = (f",fps=30,zoompan=z='1.4-0.4*min(on/12,1)':d=1:"
               f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H}:fps=30"
               if args.anim == "zoom-in" else "")

    for i, (st, dur) in enumerate(segs):
        mat, mw, mh, mdur = mat_for_seg[i]
        use_count[mat] = use_count.get(mat, 0) + 1
        off = args.start_offset + (use_count[mat] - 1) * args.reuse_offset
        off = min(off, max(0.0, mdur - dur - 0.2))
        out = os.path.join(out_dir, f"seg_{i+1:02d}.mp4")
        vf = (f"scale={BW}:{BH}:force_original_aspect_ratio=decrease,"
              f"pad={BW}:{BH}:(ow-iw)/2:(oh-ih)/2{anim_vf}")
        cmd = ["ffmpeg", "-y", "-v", "error",
               "-ss", f"{off:.3f}", "-t", f"{dur:.3f}", "-i", mat,
               "-vf", vf, "-r", "30", "-c:v", "libx264",
               "-preset", "veryfast", "-crf", "20",
               "-pix_fmt", "yuv420p", "-an", out]
        subprocess.run(cmd, check=True)
        concat_list.append(f"file '{out}'")
        work_files.append(out)
        print(f"  seg{i+1:02d}: {os.path.basename(mat)} dur={dur:.2f}s")

    list_file = os.path.join(out_dir, "concat.txt")
    with open(list_file, "w") as f:
        f.write("\n".join(concat_list) + "\n")
    silent = os.path.join(out_dir, "joined_silent.mp4")
    subprocess.run(["ffmpeg", "-y", "-v", "error",
                    "-f", "concat", "-safe", "0", "-i", list_file,
                    "-c", "copy", silent], check=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error",
                    "-i", silent, "-i", args.music,
                    "-map", "0:v:0", "-map", "1:a:0",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                    "-shortest", args.out], check=True)
    print(f"\nDONE -> {args.out}")
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration,size", "-of", "default=noprint_wrappers=1",
                        args.out], capture_output=True, text=True)
    print(r.stdout)
    if not args.keep_work:
        for f in work_files:
            try: os.remove(f)
            except OSError: pass
        for f in (silent, list_file):
            try: os.remove(f)
            except OSError: pass


if __name__ == "__main__":
    main()
