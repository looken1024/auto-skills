---
name: "douyin-beat-video"
description: "抖音卡点视频流水线:提取音轨检测节拍,Pexels找素材,ffmpeg按拍切换+入场缩放动画,素材不重复"
---

# douyin-beat-video — 抖音卡点视频流水线

用户提供一段带音乐的视频（或音频），自动提取音轨 → 检测节拍 → 从 Pexels 下载主题素材 → 按节拍点切换素材 + 入场缩放动画 → 混入原音乐输出卡点视频。

## 触发场景

- 用户发来一段视频/音频，要求做"卡点视频""跟拍""按节奏切换画面"
- 用户要求素材按主题（秋天/城市/科技等）从 Pexels 找、每段不重复
- 每段画面进入时要有动画（放大收缩到正常尺寸）

## 环境依赖

- ffmpeg 6.x（含 ffprobe），Python3 + numpy（不需要 scipy/librosa）
- Pexels API key（`config.json` 的 `pexels_api_key`，API 调用必须带浏览器 UA）
- 全部用纯 numpy 能量峰值检测节拍，无第三方音频库

## 核心流程

### 1. 提取音轨

```bash
ffmpeg -y -v error -i <用户视频> -vn -acodec pcm_s16le -ar 44100 -ac 1 /tmp/music_raw.wav
```

原视频文件保留用于最后混音（`make_beat_video.py --music <原文件>` 直接取音轨）。

### 2. 节拍检测（beat_detect.py）

```bash
python3 beat_detect.py /tmp/music_raw.wav --out beats.json
```

输出 JSON：`{"beats": [1.37, 1.97, ...], "bpm": 100, "duration": 14.79}`。

算法：分帧(50ms)算 RMS 能量 → 归一化 → 移动平均平滑(120ms) → 动态阈值(mean + k*std) → 局部峰值 → 最短间隔过滤。

**参数默认值（实测稳定）**：`--min-interval 0.45 --threshold-k 1.4`。弱拍过密时调大 threshold-k（1.6）；节奏稀疏时调小 min-interval（0.3）。

**BPM 计算**：节拍间隔直方图聚类（每个间隔按 1x/2x/0.5x 倍率投票），抗漏拍/杂散间隔干扰。

**注意**：卡点视频的节拍点 = `beats` 列表，不是 BPM 均分——直接按真实峰值切。

### 3. Pexels 素材（复用 douyin-card-pipeline 的 vsearch）

```bash
python3 scripts/card_pipeline.py vsearch "秋天" --pp 8 --res 720 --out /tmp/pexels/autumn_mats/
```

或直接调 API：`https://api.pexels.com/videos/search?query=...&per_page=8`，选 `video_files` 中**横屏且最接近目标分辨率**的版本（带浏览器 UA，否则 403）。下载到素材目录，保留原文件名。

### 4. 卡点合成（make_beat_video.py）

```bash
python3 make_beat_video.py --beats beats.json --mats <素材目录> --music <原视频> --out beat.mp4
```

流程：
1. 节拍点 → 段边界 `[0, b1, b2, ..., end]`（首段=前奏，尾段=音乐结尾）
2. 扫描素材目录，过滤竖屏（宽≥高），**每段分配独立素材**；素材不足时按 `--reuse-offset 3.0` 秒偏移复用（画面不同）
3. 每段从素材 `--start-offset 0.5`s 开始截取
4. **入场动画**（默认 zoom-in）：`zoompan=z='1.4-0.4*min(on/12,1)'` —— 从 1.4 倍放大在 0.4 秒内收缩到 1.0 倍，然后定格。`on` 是输出帧号（30fps 下 12 帧=0.4s）
5. concat 拼接 → 混入原音乐音轨（`-map 0:v -map 1:a -shortest`）

**动画关键参数公式**（30fps 输出）：
- 动画时长 T 秒 → `z='1.4-0.4*min(on/{T*30},1)'`
- 放大倍数 Z → 起始 `Z`，结束 1.0：`z='{Z}-{Z-1}*min(on/{T*30},1)'`
- 关闭动画：`--anim none`

### 5. 微信交付压缩

微信对视频消息有大小/规格限制，发送前压缩：

```bash
ffmpeg -y -v error -i beat.mp4 -c:v libx264 -profile:v baseline -level 3.0 \
  -preset fast -crf 26 -pix_fmt yuv420p -c:a aac -b:a 96k -ar 44100 -ac 2 \
  -movflags +faststart beat_small.mp4
```

## 脚本

- `scripts/beat_detect.py` — 节拍检测（纯 numpy）
- `scripts/make_beat_video.py` — 卡点合成器（通用配置）

```bash
python3 beat_detect.py <music.wav> [--out beats.json] [--min-interval 0.45] [--threshold-k 1.4]
python3 make_beat_video.py --beats beats.json --mats <dir> --music <video> \
  --out out.mp4 [--anim zoom-in|none] [--res 1280x720] [--min-seg 0.4] \
  [--start-offset 0.5] [--reuse-offset 3.0] [--keep-work]
```

## 坑点备忘（血泪）

- **crop 滤镜不支持时间变量**：`crop=w='...min(t/0.6,1)...'` 只在初始化求值一次，动画不生效，两个不同表达式产出的文件 md5 完全相同。缩放动画**必须用 zoompan**（每帧实时求值）
- zoompan 配合 `fps=30` 前置：`scale=1600:900,pad,fps=30,zoompan=...:s=1280x720:fps=30`，不然帧数/时长会丢
- zoompan 输出尺寸由 `s=` 参数决定，前面 scale 到 1.25 倍工作区（1600x900）保证 1.4x 缩放有富余不露边
- Pexels API 必须带浏览器 UA（`Mozilla/5.0 ... Chrome/126.0`），urllib 默认 UA 403
- 竖屏素材要过滤（`width >= height`），否则卡点视频里出现黑边
- 各段时长应 ≥0.4s，过短的段（前奏弱拍）要合并/丢弃，否则 0.1s 闪切
- 素材复用偏移 `min(off, 素材时长-段时长-0.2)` 防止截断
- ffmpeg `-ss` 放 `-i` 前（输入定位，快）且配合 `-t`
- concat 列表文件必须 `-safe 0`；各段编码参数必须完全一致（同分辨率/帧率/像素格式），否则 concat copy 会花屏
- 微信视频发送可能被限流（`sendMessage ret=-2 errmsg=prepare failed`），短时间连续发多条视频会触发风控，等几分钟再发；压缩到 5-8MB 成功率更高

## 已验证明细（2026-08-29 秋天卡点）

- 用户视频：14.8s，720×1280 竖屏 HEVC+AAC → 提取 44.1kHz 单声道 wav
- 检测：18 拍（含前奏），主间隔 0.6s → BPM 100，实际使用 17 拍（合并 0.07s 首段弱拍）
- 素材：Pexels 搜 "autumn leaves/forest/trees" 等，19 个横屏素材 → 18 段每段独立素材
- 输出：1280×720@30fps，14.79s，zoompan 1.4x→1.0x @0.4s 入场动画
- 验证动画：段内前 0.4s 帧差异 30+（缩放中），后 0.2s 差异 1.3（定格）
