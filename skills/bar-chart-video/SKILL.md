---
name: "bar-chart-video"
description: "生成数据随时间动态变化的对比视频(动态条形图排行榜,如人口/经济/流量排行)。模板化渲染:JSON数据+JSON模板→PIL逐帧绘制→ffmpeg合成MP4。零第三方依赖(仅Pillow+ffmpeg)。触发词:动态条形图/动态排行视频/bar chart race/population ranking video。"
---

# Bar Chart Video - 动态条形图排行视频生成器

把"随时间变化的数据排行"做成短视频(如抖音/GIF/视频号常见的"XX国人口预测排行")。
**模板驱动**:数据 JSON + 模板 JSON → 脚本自动渲染逐帧 → ffmpeg 合成 MP4。

## 触发场景

用户说:
- "生成这种数据随时间动态变化的对比视频"
- "做个动态条形图排行:XX国XX数据 2015-2025"
- "这种人口预测排行视频怎么做"
- "bar chart race"

## 工作流程

### Step 1:准备数据 JSON

格式(`data.json`):

```json
{
  "title": "五国人口预测排行",
  "subtitle": "数据来源: FAO | 单位: 千人",
  "start_year": 2015,
  "end_year": 2025,
  "items": [
    {"name": "印度", "color": "#ff9933", "values": [1322866, 1339160, ...]},
    {"name": "中国", "color": "#de2910", "values": [1393715, 1400050, ...]}
  ]
}
```

- `values` 数量必须 = `end_year - start_year + 1`
- 数据来源要真实,可联网核验(FAO/世界银行/UN DESA)
- 颜色用十六进制,每个国家固定一个

### Step 2:选模板

`templates/` 内置:
- `population_dark.json` — 深色竖版(1080×1920),仿短视频人口排行风格

可复制改造成新模板:
- `width/height`:画布(手机竖版 1080×1920;横版 1920×1080)
- `bg_color/title_color/...`:配色
- `bar_height/bar_gap`:条形粗细间距
- `year_position`:年份大数字位置(相对坐标 0~1)
- `bar_area_top/bottom`:条形区上下边界(相对坐标)
- `fps/duration_per_year`:帧率、每年时长(秒)
- `max_value_scale`:条形最大长度余量(1.15=留15%)
- `show_rank/show_value`:是否显示排名数字、条尾数值

### Step 3:生成视频

```bash
python3 scripts/bar_chart_video.py data.json templates/population_dark.json output.mp4 \
  [--fps 30] [--duration-per-year 0.8] [--width 1080] [--height 1920] [--keep-frames]
```

输出 1080×1920 竖版 MP4,可直接发视频号/抖音。

### Step 4:质量检查(硬性)

1. **视频存在且非空**:`ls -la output.mp4`,>100KB 为正常
2. **抽查帧内容**:`ffmpeg -ss <时间点> -i output.mp4 -frames:v 1 frame.png`,用视觉模型检查文字是否溢出、条形是否越界、中文是否正常
3. **数值肉眼核验**:终帧数值应与数据 JSON 一致
4. 文字溢出时:调 `value_size`/`bar_area_bottom`/`max_value_scale`

## 参数调优速查

| 现象 | 改哪里 |
|---|---|
| 条尾数值被截断 | `bar_area_bottom` 调大 / `value_size` 调小 / `max_value_scale` 调大 |
| 条太短 | `max_value_scale` 调小(1.1→1.05) |
| 年份数字太小 | `year_size` 调大 |
| 视频太长 | `duration_per_year` 调小 / `fps` 调低 |
| 排名位置挤 | `rank_font_size` 调小 |

## 依赖

- Python3 + Pillow(`python3 -c "import PIL"`)
- ffmpeg(`command -v ffmpeg`)
- 中文字体(Noto Sans CJK,系统已装;macOS PingFang、Windows 微软雅黑自动探测)
- **无 matplotlib 依赖**(PIL 逐帧绘制,内存友好,1.9G 小内存机器可跑)

## 踩坑记录

- `pip install matplotlib` 在 Ubuntu 24.04 会被 PEP 668 拦,apt 又可能被小内存 SIGKILL → **直接用 PIL,零新增依赖**
- 中文字体 `.ttc` 用 `ImageFont.truetype()` 直接加载即可,PIL 支持 ttc
- 每帧保存 PNG 再 ffmpeg 合成,帧数多时用 `--keep-frames` 便于排查;正常跑完自动清理临时帧
- 数值插值用线性过渡,首年直接到位,排序随值动态变化 → 呈现"排行洗牌"效果