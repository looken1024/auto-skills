---
name: "data-chart-scripting"
description: "Use when 用真实数据脚本画折线/柱状图并加标题。真实取数+matplotlib+视觉评审。"
---

# 用脚本把真实数据画成出版级图表

用户说「给我找一份数据，按年份做个漂亮的折线图，加标题，最好用脚本做」时走这条路。
产出：**一个可重跑的「取数 + 绘图」脚本** + **一张成图**（PNG，用 `MEDIA:/abs/path.png` 发给用户）。

> 姊妹技能 `bar-chart-video`（用户自有）管**动态条形图视频**（PIL 逐帧 + ffmpeg）。
> **静态图走 matplotlib，不要套视频那条路。** 该技能里「matplotlib 装不上」的说法已被本技能实测推翻。

## 触发场景

- "找一份数据，按年份画个漂亮的折线图 / 柱状图，加标题"
- "用脚本生成一张图表" / "把 XX 数据可视化一下"
- "找点奇奇怪怪、随时间变化的数据"（→ 见 `references/time-series-data-sources.md`，含专门收集怪数据集的网站）

## 硬性铁律

1. **数据必须真实取用，不得编造。** 取不到就直说取不到，或换源。
2. **变化在图表量程下看不见时，禁止在标题/副标题里夸大它。**（见第 5 节「诚实原则」）
3. **出图后必须过一遍视觉评审**，按反馈迭代后再交付。（见第 6 节）

## 1. 选数据（先看曲线有没有故事）

优先**有拐点 / 反超 / 反转**的曲线——单调上升最平庸。
本机实测可用的免 key 时序源（附实测值）见 `references/time-series-data-sources.md`。

取数**用 `subprocess` + `curl`**：本机必须走全局代理，`curl` 继承环境变量直接可用，`urllib` 即便带代理也容易 TLS 超时。
世界银行：`https://api.worldbank.org/v2/country/<ISO3>/indicator/<ID>?format=json&per_page=400`
（返回 `[meta, [{date, value}, ...]]`；`value` 可能为 null 要滤掉、年份要排序）。

## 2. 装环境（本机实测 2026-10-03）

```bash
python3 -m venv /home/ubuntu/.venvs/plot
/home/ubuntu/.hermes/bin/uv pip install --python /home/ubuntu/.venvs/plot/bin/python matplotlib
# → matplotlib 3.11.2
```

- venv 里**裸 `pip install matplotlib` 会失败（找不到包）**，只有 `uv` 行得通。系统 pip 被 PEP 668 拦，别去动。
- 跑图：`/home/ubuntu/.venvs/plot/bin/python your_chart.py`
- 已知可用成例（含完整注释）：`/home/ubuntu/charts/cn_population_line.py`

## 3. 中文字体（不注册 = 中文标题全方块）

```python
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

p = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"   # 本机实测存在
font_manager.fontManager.addfont(p)
plt.rcParams["font.family"] = font_manager.FontProperties(fname=p).get_name()
plt.rcParams["axes.unicode_minus"] = False
```

wqy 只有 weight 500，要 bold 时会打 `findfont: Failed to find font weight bold` 并 fallback，**显示正常，忽略即可**。

## 4. 样式清单（用户认可的那一版）

画布暖白 `#faf8f5`；主色砖红 `#c8442c`；正文 `#22201d`；次级 `#8a857d`；极淡 `#c3bdb4`；网格 `#e6e0d8`。

- **标题**：左对齐、25pt 左右、粗、置于绘图区上方
- **副标题只讲趋势，不要重复标注里已有的数字和年份**（第一次评审就因重复被扣分）
- **来源脚注**：底部小字「数据来源：世界银行 World Bank Open Data（指标 ID），取数于 <日期>」——日期用 `time.strftime("%Y-%m-%d")` **动态取**，别硬编码
- **曲线下方渐变填充**：不是简单 alpha 色块，而是铺一条渐变 `imshow` 再按曲线路径 `set_clip_path` 裁切（代码见 references）
- **标注**：全部统一成「年份 + 数值」同一格式，带细引线
- **峰值**单独画点：`ax.plot(..., "o", ms=8.5, mec=BG, mew=2.2)`
- **轴**：隐藏 top/right/left spine；只留极淡横向网格（`set_axisbelow(True)`）；y 轴只给 3~4 个参考刻度且标签颜色比刻度线更弱；x 轴只标整十年 + 末年
- 单位写在轴角落「单位：亿」，不要塞进标题

细节代码与内嵌放大图写法见 `references/matplotlib-setup-and-style.md`。

## 5. 诚实原则（硬性 · 用户口味的核心）

**数据变化在图表量程下肉眼不可见时，禁止用标题/副标题夸大它。**

实例：中国人口 1960–2025，峰值 2021（14.1236 亿）→ 2025（14.0658 亿），降幅只有 **0.41%**。在 6.67–14.12 的量程上主图几乎是直线，此时写「掉头向下」就是拿数据说假话。正确做法：

- 加 **`ax.inset_axes()` 局部放大图**（放留白处，如左上角；本次用 `[0.075, 0.565, 0.285, 0.315]`），标题写「2021 年后，连续四年回落」，把拐点摊开
- 副标题只写得住的事实（「六十年间增长了一倍多，拐点刚刚开始」）
- 见顶后那一段用更深/更粗的颜色单独加深，视觉上标出来

宁可说「变化很小」，也不要让图说谎。

## 6. 出图后视觉评审（硬性）

```
vision_analyze(图路径,
  "设计评审：1.中文有无方块乱码 2.标题/副标题/标注/来源/内嵌图有无重叠或出界
   3.内嵌图是否压住主曲线 4.打分(1-10)并给出还需修的具体问题")
```

按反馈改 → 重跑 → 再审。本次实测：第一轮 8 分（副标题与峰值标注信息重复、内嵌图与主曲线有挤压感、y 轴无刻度）→ 修完 9 分「无必须修的问题」。

⚠️ 视觉模型会**反复把正确的「取数日期」当成「未来日期笔误」**——先跑 `date` 核对系统日期，确认是笔误才改，别被它带偏。

## 7. 交付

- 成图 + **脚本路径**都告诉用户，并说清数据源与关键数字（哪年见顶、变了多少）
- 把 `INDICATOR` / `COUNTRY` 提成模块级常量，用户换主题时改一行就行；主动告知这一点
- 图用 `MEDIA:/abs/path.png` 直接发

## 已知坑

- **venv 里 `pip install` 失败 ≠ 装不上** → 换 `uv pip install --python <venv>/bin/python <pkg>`
- **中文变方块** → 忘了 `font_manager.addfont()`（PIL 那套 `ImageFont.truetype()` 的经验不能直接搬）
- **渐变填充变成实心色块** → `set_clip_path` 传的 patch 必须带 `transform=ax.transData`
- **取数日期被当成笔误** → 用 `date` 核对，别改
- **直连超时** → 本机必须走全局代理，拉数据统一走 `curl`

## 参考

- `references/matplotlib-setup-and-style.md` — 环境、字体、样式与内嵌放大图的完整代码
- `references/time-series-data-sources.md` — 实测可用的时序数据源（免 key API + 实测值）、怪数据集专门站、代理坑
