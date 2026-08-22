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
- "这种人口预测排行视频怎么做" / "bar chart race"
- "按每年真实前N展示"

## 工作流程(核心:模型只算首尾帧,中间帧脚本生成)

### Step 1:准备数据 JSON

格式(`data.json`):

```json
{
  "title": "世界人口前五 1975-2025",
  "subtitle": "数据来源: 世界银行 | 单位: 万人 | 每年动态取前5",
  "start_year": 1975,
  "end_year": 2025,
  "items": [
    {"name": "印度", "color": "#FF8C00", "values": [61131, 62370, ...]},
    {"name": "中国", "color": "#E63946", "values": [91640, 92840, ...]}
  ]
}
```

要点:
- `values` 数量必须 = `end_year - start_year + 1`
- **数据来源要真实可核验**:优先 World Bank API(SP.POP.TOTL),少见数据用 UN DESA/FAO。拉真实数据:`https://api.worldbank.org/v2/country/<ISO3;ISO3...>/indicator/SP.POP.TOTL?format=json&date=1975:2025&per_page=1200`(国家码分号分隔;`SUN` 苏联等历史实体码可能非法,需用加盟国求和)
- **颜色**:每"实体"一个专属色,全程固定不变(排序变化颜色跟着国家走,不随排名变)。高区分度配色示例:中国红 #E63946 / 印度橙 #FF8C00 / 美国蓝 #277DA1 / 苏联紫 #9B5DE5 / 印尼青绿 #06A77D / 巴西金黄 #F9C74F / 巴基斯坦薄荷绿 #43AA8B / 尼日利亚黄绿 #90BE6D
- **单位选择影响观感**:数字位数越多变化越明显。人口用"万人"(6位数)比"亿人"(2-3位)视觉冲击强 10 倍
- **动态前N**:模板 `top_n: 5` 开启"每年取真实前N",国家可进出榜;候选需覆盖所有可能入榜者(如世界前5要备20国),历史实体(苏联)单独处理

### Step 2:数据校验(硬性,先于生成)

```bash
python3 scripts/validate_data.py data.json --top 5
```

校验脚本输出:结构检查(values数量/负数/全0)+ 逐年 Top N + **进出榜事件** + **榜首更替** + 突变检测(-50%~+50%)。

**必须把校验报告 + 关键转折点交给模型交叉审**(像公众号 AI 味终检一样),重点核历史事实:
- 苏联 1991 年 12 月解体 → 1992 起必须从前N消失(不是 bug,是史实!)
- 榜首更替年份与真实历史吻合(2021-2023 印度反超中国)
- 进出榜事件合理(如 2009 前后巴基斯坦超巴西)
- 数值量级合理(中国/印度长期 10亿+、美国 3亿+)

校验通过后才进入渲染;有问题先修数据。

### Step 3:选模板

`templates/` 内置:
- `population_landscape.json` — **横版 16:9(1920×1080)**,默认,年份大字右上角
- `population_dark.json` — 竖版 9:16(1080×1920),仿短视频风格

模板可改:
- `width/height`:画布;系统按宽≥高自动横/竖布局
- `bg_color/title_color/...`:配色
- `bar_height/bar_gap`:条形粗细间距
- `year_position`:年份位置(相对坐标;横版自动右上角按 textlength 右对齐)
- `bar_area_top/bottom`:条形区上下边界(相对坐标)
- `fps/duration_per_year`:帧率、每年时长(秒)
- `max_value_scale`:条形最大长度余量(**1.02** 让最长条接近满宽,数值才贴右边界)
- `value_scale_mode`: `per_frame`(默认,每帧相对当年最大缩放,条长严格随数据比例变化、最大条满宽) / `global`(全片统一比例)
- `top_n`: 每年动态取前N(None=全部)
- `end_pause`: 结尾定格秒数(如 2)
- `show_rank/show_value`:是否显示排名、数值

### Step 4:preview 质检(硬性)

```bash
# 1) 预览:只渲染首帧+尾帧 PNG(不生成视频)
python3 scripts/bar_chart_video.py data.json templates/population_landscape.json out.mp4 --preview
# 生成 out_start.png + out_end.png

# 2) 视觉模型检查两帧:
#    - 文字越界/截断/重叠
#    - 条形超界
#    - 数值垂直居中、紧贴条尾、与条形无重叠
#    - 最长条数值贴右边界(小间隔)不越界
#    - 中文正常
#    通过 → 全量;不通过 → 调模板参数重跑 preview

# 3) 全量生成(去掉 --preview)
python3 scripts/bar_chart_video.py data.json templates/population_landscape.json out.mp4 \
  --fps 10 --duration-per-year 1.0 --end-pause 2
```

首尾帧是"极值帧"(首年排序+末年排序),通过即代表全片布局基本安全;中间帧全部脚本线性插值,不经模型。

### Step 5:成品抽检

1. `ls -la out.mp4`,>100KB 为正常
2. 抽中段关键帧(如进出榜转折年):`ffmpeg -ss <秒> -i out.mp4 -frames:v 1 f.png`,视觉模型确认动态避让/贴边无异常
3. 终帧数值与数据 JSON 一致

## 动态布局原理(脚本已实现,勿回退)

- **条形起点** = max(基准起点, 最宽国家名右缘 + 12px) → 国家名永不被条形覆盖(2009 巴基斯坦入榜后文字不被挡)
- **条形最大宽** = 数值右缘上限 − 数值文本宽 − 8px − 条形起点 → **条形永远到不了数值区域**,最长条时条形尾与数值间留 8px,数值始终在条形右侧
- **数值 x** = 条形尾 + 8px(紧贴条尾,随条长按比例移动;短条时位于画面中部,仅最大时触右边界)
- **数值钳位** = 右缘不超过 `bar_right_limit - 8`
- **垂直居中** = `textbbox` 实测字形包围盒,非 `font_size/2` 近似(中文字体基线差异大,近似会偏)
- 横版 `bar_right_limit` = W×0.97(数值贴边),竖版 W×0.93

## 参数调优速查

| 现象 | 改哪里 |
|---|---|
| 最长条数值离右边界远 | `max_value_scale` 收到 1.02~1.05 / `bar_right_limit` 加大 |
| 最长条与数值重叠 | 确认条形最大宽已减数值宽(勿只减 8px) |
| 数值偏高偏低 | 用 textbbox 居中,勿用 font_size/2 |
| 数值被截断 | `bar_area_bottom` 调大 / `value_size` 调小 / `bar_right_limit` 调小 |
| 国家名被条挡 | 条形起点已自动避让;label_font_size 过大时调小 |
| 年份数字太小 | `year_size` 调大 |
| 视频太长 | `duration_per_year` 调小 / `fps` 调低 |

## 依赖

- Python3 + Pillow + ffmpeg(无 matplotlib,`pip install matplotlib` 在 Ubuntu 24.04 被 PEP 668 拦,apt 又可能被小内存 SIGKILL → 纯 PIL 逐帧,1.9G 内存可跑)
- 中文字体 Noto Sans CJK(系统已装;macOS PingFang / Windows 微软雅黑自动探测);`.ttc` 用 `ImageFont.truetype()` 直接加载

## 踩坑记录(实战沉淀)

1. **matplotlib 装不上** → PEP 668 + 小内存(1.9G apt 被 SIGKILL)→ 纯 PIL 渲染,零新增依赖
2. **中文字体** → `ImageFont.truetype()` 直接吃 `.ttc`;PIL 支持
3. **模型 API 抖动** → opencode.ai/zen/go 偶发 Internal server error / 空白响应,换模型重试(deepseek-v4-flash-vision-exp ↔ qwen3.8-max);curl 命令中 `$(cat key)` 会被工具脱敏破坏 → 用 python 脚本内读 key + subprocess 调 curl
4. **单位影响观感** → 亿→千万→万,数字大 10 倍变化更明显;人口排行用"万人"最清晰
5. **历史实体** → 苏联 1991 解体前是世界第3,直接用 RUS 数据会"俄罗斯"提前上榜(史实错误);要算苏联整体=俄罗斯+14加盟国求和,1992 后置 0 让其自然退出;RUS 1992 前也置 0 避免单列
6. **World Bank API** → 国家码非法(如 SUN)会整单 400;多国用分号拼;苏联各加盟国单独可查
7. **条长固定不变坑** → 早期用全局最大值做比例,条长几乎不动;改 `per_frame`(每帧相对当年最大)后条长严格随数据比例变化,洗牌感强
8. **数值与条形重叠** → 条形最大宽必须扣除数值文本宽+8px(只减 8px 会重叠);数值钳位在右界内
9. **数值垂直居中** → `d.textlength` 只给宽不给高,字体基线不同;用 `d.textbbox((0,0), text, font=font)` 取包围盒居中
10. **横版年份** → 右上角用 `d.textlength` 量宽右对齐,避免年份位数变化漂移
11. **进出榜渐变** → 第6名渐隐是插值+取前N的自然效果,视觉正常;国家从 0 增长上榜①平滑
12. **preview 模式** → 先首尾帧质检再全量,省模型额度;首尾帧是极值帧,通过≈全片安全
13. **帧清理** → 每帧 PNG 存临时目录,跑完自动删;`--keep-frames` 排查用
14. **结尾定格** → `--end-pause 2` 复制终帧 N 秒,比慢速循环更自然