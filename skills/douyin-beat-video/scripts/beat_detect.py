#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""节拍检测: 从 wav 提取能量包络 → 峰值检测 → 节拍点列表 + BPM
用法: python3 beat_detect.py music.wav [--out beats.json]
纯 numpy 实现, 无 scipy/librosa 依赖
"""
import argparse, json, sys
import numpy as np
import wave


def load_wav(path):
    w = wave.open(path, 'rb')
    sr = w.getframerate()
    ch = w.getnchannels()
    n = w.getnframes()
    raw = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float64)
    if ch > 1:
        raw = raw.reshape(-1, ch).mean(axis=1)
    return raw, sr, n / sr


def detect_beats(path, hop=0.05, smooth=0.12, min_interval=0.45,
                 threshold_k=1.4, min_energy=0.04):
    data, sr, dur = load_wav(path)
    frame = int(sr * hop)
    n_frames = max(1, len(data) // frame)
    energy = np.zeros(n_frames)
    for i in range(n_frames):
        seg = data[i*frame:(i+1)*frame]
        energy[i] = np.sqrt(np.mean(seg**2)) if len(seg) else 0.0
    mx = energy.max()
    if mx > 0:
        energy /= mx
    # 平滑包络
    win = max(1, int(smooth / hop))
    kernel = np.ones(win) / win
    env = np.convolve(energy, kernel, mode='same')
    # 动态阈值
    thr = env.mean() + threshold_k * env.std()
    thr = max(thr, min_energy)
    # 局部峰值
    beats = []
    i = 1
    step = max(1, int(min_interval / hop))
    while i < len(env) - 1:
        if env[i] > thr and env[i] >= env[i-1] and env[i] >= env[i+1]:
            t = round((i + 0.5) * hop, 3)
            if not beats or t - beats[-1] >= min_interval:
                beats.append(t)
                i += step
                continue
        i += 1
    # BPM: 用间隔直方图聚类找主拍间隔(抗漏拍/杂散间隔)
    bpm = None
    if len(beats) >= 3:
        diffs = np.diff(beats)
        grid = np.arange(0.2, 2.0, 0.05)
        hist = np.zeros_like(grid)
        for d in diffs:
            idx = np.argmin(np.abs(grid - d))
            for mult in (1.0, 2.0, 0.5):
                j = np.argmin(np.abs(grid - d * mult))
                if abs(d * mult - grid[j]) < 0.08:
                    hist[j] += 0.5
            hist[idx] += 1.0
        main = grid[np.argmax(hist)]
        bpm = round(60.0 / main, 1)
    return {'beats': beats, 'bpm': bpm, 'duration': round(dur, 3),
            'sample_rate': sr, 'hop': hop}


def main():
    ap = argparse.ArgumentParser(description='numpy 能量峰值节拍检测')
    ap.add_argument('wav', help='输入 wav 文件(16bit PCM)')
    ap.add_argument('--out', default='beats.json', help='输出 json')
    ap.add_argument('--min-interval', type=float, default=0.45, help='最短节拍间隔(秒)')
    ap.add_argument('--smooth', type=float, default=0.12)
    ap.add_argument('--threshold-k', type=float, default=1.4, help='阈值倍数(越大拍越少)')
    args = ap.parse_args()
    res = detect_beats(args.wav, min_interval=args.min_interval,
                       smooth=args.smooth, threshold_k=args.threshold_k)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    with open(args.out, 'w') as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    print(f'BPM={res["bpm"]} beats={len(res["beats"])} duration={res["duration"]}s -> {args.out}',
          file=sys.stderr)


if __name__ == '__main__':
    main()
