---
name: "topic-video-pipeline"
description: "主题→短视频流水线：钩子标题候选→免费素材搜索验证→ffmpeg竖版合成→TTS配音→免费BGM。太空科普优先"
---

# 主题短视频自动生成（Topic-to-Video Pipeline）

给定一个主题（如"人类最远的声音"、"火星蓝色日落"），自动产出一条抖音风格竖版短视频。用户已验证：视频不带正文字幕，只要顶部标题+副标题，8 秒左右，可加 BGM/配音。

## 成品规格（用户确认过的标准）

- 竖版 1080×1920，30fps，8-60 秒
- 顶部红色大标题（白描边）：fontsize 86，y=h*0.106（约占屏高 4.3%）
- 副标题黄色底框黑字：fontsize 75（占屏宽约 70%），y=h*0.156，boxborderw=16
- 副标题宽度超屏时要降到该值；校准方法见"合成"节
- 无正文字幕（除非用户要求）
- 画面：原图/原视频居中 + 上下模糊暗色背景（gblur sigma=30, brightness=-0.28）
- 运镜：zoompan 缓慢推近（z='min(zoom+0.0016,1.25)'）
- BGM 截取到视频时长

## 流程（5 步）

### 1. 标题生成（钩子+悬念，主标题+副标题一对）

风格要点：
- 主标题：短句钩子，制造好奇/反差（如"人类最远的声音"、"月球上没有风"）
- 副标题：补充悬念/反转（如"已经在太空飘了40多年"、"脚印能留一千年"）
- 一次给 5-8 条候选，分主题组（哲思/历史/冷知识/未来），让用户选，不要直接开做
- 避免 AI 味：不要"在这个浩瀚的宇宙中""让我们一起来探索"这类废话

历史已验证候选示例（2026-08-23）：
- 宇航员在月球上看地球 / 为何有人看完会沉默
- 人类最远的声音 / 已经在太空飘了40多年（已采用）
- 光从太阳到地球 / 需要8分20秒
- 宇宙里有4000亿个太阳系 / 而我们只找到一个家
- 月球车拍到的画面 / 人类第一次见到

### 2. 素材搜索（NASA 官方图库，免费可商用）

NASA 搜索 API（无需 key）：
```bash
# 搜视频
curl -s 'https://images-api.nasa.gov/search?q=KEYWORD&media_type=video&page_size=8' | python3 -m json.tool
# 搜图片
curl -s 'https://images-api.nasa.gov/search?q=KEYWORD&media_type=image&page_size=8' | python3 -m json.tool
```

拿资源链接：
```bash
curl -s "https://images-api.nasa.gov/asset/NASA_ID" | python3 -c "
import json,sys
d=json.load(sys.stdin)
for it in d.get('collection',{}).get('items',[]):
    print(it.get('href'))"
```

下载（高清优先：~orig > ~large > ~medium；视频用 ~orig/~medium，图片用 ~orig）：
```bash
curl -sL -o out.mp4 "http://images-assets.nasa.gov/video/NASA_ID/NASA_ID~medium.mp4"
curl -sL -o out.jpg "http://images-assets.nasa.gov/image/NASA_ID/NASA_ID~orig.jpg"
```

关键 NASA 素材 ID（已验证）：
- Apollo 11 登月：Apollo_11_moonwalk_montage_720p（120s/720p，40-80s 宇航员行走，100-120s 登月舱+月球车）
- 猎户座看地月：art001m1013321410_1
- LRO 月球表面：GSFC_20110617_LRO_m10794_Temp
- 旅行者号金唱片图：PIA14113、PIA21741；飞船图 PIA14111、PIA17045
- ISS 地球视角：NHQ_2019_0626_Earth Views from the ISS

搜索词建议：常用 `voyager`、`apollo 11`、`earth from moon`、`moon surface`、`golden record`、`interstellar space`。

坑：NASA 视频有多个清晰度变体（orig/large/medium/mobile/small），mobile 只有 320×180，务必下载高清版；原声可忽略（后面会被 BGM 覆盖）。

### 3. 素材验证（qwen-vl-max 视觉检查）

用 DashScope qwen-vl-max 检查图片/抽帧：画面主体对不对、清晰度够不够、有没有变形。见 scripts/vl_check.sh。不要盲目相信文件名。

竖版素材视频要抽帧选段：`ffmpeg -i in.mp4 -vf "fps=1/5,scale=480:-1" -q:v 3 f_%02d.jpg`，然后批量问视觉模型"哪几帧有清晰宇航员/主体"。

### 4. 合成（纯 ffmpeg 管线，勿用 Python 逐帧）

⚠️ 关键教训：Python PIL 逐帧渲染 1080×1920 会被系统 SIGKILL（内存爆）。必须用纯 ffmpeg filter_complex。

单图/视频 → 竖版 + 标题 + BGM 模板见 scripts/make_vertical.sh，核心 filter：
```
split=2[bg][fg];
[bg]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,
gblur=sigma=30,eq=brightness=-0.28:saturation=0.85[bgb];
[fg]scale=1080:-2[fg2];
[bgb][fg2]overlay=(W-w)/2:(H-h)/2[base];
[base]zoompan=z='min(zoom+0.0016,1.25)':d=240:s=1080x1920:fps=30,
drawtext=fontfile=FONT:textfile=title.txt:fontsize=86:fontcolor=red@0.95:
x=(w-text_w)/2:y=h*0.106:borderw=6:bordercolor=white,
drawtext=fontfile=FONT:textfile=sub.txt:fontsize=75:fontcolor=black:
x=(w-text_w)/2:y=h*0.156:box=1:boxcolor=yellow@0.98:boxborderw=16
```

字体：/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc
多段视频拼接：先各段转竖版无声（同上 filter，-r 30 -c:v libx264），再 concat demuxer 拼接，最后统一 drawtext（enable='between(t,t0,t1)' 控制每句字幕时间）。

标题尺寸校准方法（用户对比例敏感，务必先校准）：
```bash
ffmpeg -y -f lavfi -i color=black:s=1080x1920:d=1 -vf "drawtext=fontfile=FONT:textfile=sub.txt:fontsize=FS:x=(w-text_w)/2:y=100:box=1:boxcolor=yellow@1:boxborderw=8" -frames:v 1 cal.png
```
然后 PIL 量黄框像素宽度，目标 = 屏幕宽度 70%（1080→约 756px）；fontsize 75 时"已经在太空飘了40多年"= 72% 已验证 OK。

### 5. 增强：配音 + BGM

#### BGM（免费可商用，archive.org 已验证可直连）
archive.org 搜 Jamendo 音乐（CC 授权）：
```bash
curl -s "https://archive.org/advancedsearch.php?q=space+cinematic+epic&fl[]=identifier&fl[]=title&rows=15&output=json"
# 元数据拿文件列表
curl -s "https://archive.org/metadata/IDENTIFIER" | python3 -m json.tool
# 下载：https://archive.org/download/IDENTIFIER/FILENAME（注意 URL 编码空格等）
```

已验证 BGM（Jamendo 授权，免费可商用）：
- soundbay《Pulsar》(jamendo-559406) — 太空史诗预告风，有冲击力
- SiJ《Deep In Space》(jamendo-129509) — 深邃氛围
- Yukikaze《It's the Future》(jamendo-141406) — 未来电子感（用户选定）

合成 BGM（截取视频时长）：
```bash
ffmpeg -y -i video.mp4 -i bgm_full.mp3 -t 8 -map 0:v -map 1:a -c:v copy -c:a aac -b:a 192k -shortest out.mp4
```

坑：Pixabay 有 Cloudflare 防护，curl/浏览器都难直连；archive.org 完全开放。抖音站内热门 BGM 是商业版权，不要抓取使用（限流/侵权风险）。

#### 配音（DashScope 音色克隆，用户已建音色）

克隆音色（一次性）：
```bash
curl -X POST 'https://dashscope.aliyuncs.com/api/v1/services/audio/tts/customization' \
  -H "Authorization: Bearer $DASHSCOPE_API_KEY" -H "Content-Type: application/json" \
  -d '{"model":"voice-enrollment","input":{"action":"create_voice","target_model":"qwen-audio-3.0-tts-flash","prefix":"myvoice","url":"data:audio/wav;base64,..."}}'
```
返回 output.voice_id。参考音频要求：≥10 秒干净人声，wav/mp3 均可（转 24000Hz 单声道）。

用克隆音色合成（需 dashscope SDK）：
```bash
pip3 install -q --break-system-packages -i https://pypi.tuna.tsinghua.edu.cn/simple dashscope websocket-client
```
```python
import dashscope
from dashscope.audio.tts_v2 import SpeechSynthesizer
dashscope.api_key = os.environ["DASHSCOPE_API_KEY"]
syn = SpeechSynthesizer(model="qwen-audio-3.0-tts-flash", voice="VOICE_ID")
audio = syn.call("文本")
open("out.mp3","wb").write(audio)
```

已建音色（2026-08-23）：qwen-audio-3.0-tts-flash-sci-5010260f9f3b415f90b68c69f920fa24（来自用户提供的科学探索飞船旁白视频）

备选：edge-tts（无需 key，zh-CN-YunyangNeural 播音腔）`edge-tts --voice zh-CN-YunyangNeural --text "..." --write-media out.mp3`

坑：系统 pip 受 PEP 668 保护需 --break-system-packages；DashScope HTTP TTS 接口参数易错，优先官方 SDK；克隆音色与合成模型必须一致（qwen-audio-3.0-tts-flash）。

## 工作流铁律（用户偏好）

1. 标题先给候选让用户选，选了才开做
2. 合成前先用黑底校准帧量标题/副标题尺寸（用户对比例敏感）
3. 文案/标题禁 AI 味（无感叹号堆砌、无空洞排比）
4. 素材只用免费可商用源（NASA、archive.org/Jamendo），并告知用户来源
5. 交付后给下一步选项（调比例/换 BGM/加配音/换素材）

## 交付清单
- 成品 mp4（竖版 1080×1920，8-60s）
- 说明用的素材 ID、标题文本、BGM 曲目
- 用户确认后可固化模板参数
