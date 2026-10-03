# matplotlib 环境 / 字体 / 样式代码

本文件是 `data-chart-scripting` 的代码附录。已在本机实测（Ubuntu 24.04，python3.11，1.9G 内存）。

## 环境

```bash
python3 -m venv /home/ubuntu/.venvs/plot
/home/ubuntu/.hermes/bin/uv pip install --python /home/ubuntu/.venvs/plot/bin/python matplotlib
# → matplotlib 3.11.2
```

- venv 里**裸 `pip install matplotlib` 会失败**（报找不到包）；`uv` 一次成功。
- 系统 pip 被 PEP 668 拦，不要用 `--break-system-packages` 去绕。
- 纯 PIL 路径（`bar-chart-video`）与 matplotlib 并存，互不影响。

## 字体

```python
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

p = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"
font_manager.fontManager.addfont(p)
plt.rcParams["font.family"] = font_manager.FontProperties(fname=p).get_name()
plt.rcParams["axes.unicode_minus"] = False
```

本机实测存在 `/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc`（文泉驿正黑）。
要 bold 时会打 `findfont: Failed to find font weight bold`（wqy 只有 weight 500）并 fallback，**显示正常，忽略**。

## 配色常量（用户认可）

```python
ACCENT = "#c8442c"   # 主折线（砖红）
AFTER  = "#8c2b18"   # 见顶后那一段（更深的红）
INK    = "#22201d"
MUTED  = "#8a857d"
FAINT  = "#c3bdb4"
BG     = "#faf8f5"   # 画布暖白
GRID   = "#e6e0d8"
```

## 曲线下方渐变填充（不是 alpha 色块）

```python
import numpy as np
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import PathPatch
from matplotlib.path import Path

grad = np.linspace(0, 1, 256).reshape(-1, 1)
cmap = LinearSegmentedColormap.from_list("g", ["#ffffff00", ACCENT + "40"])
im = ax.imshow(grad, extent=[years.min(), years.max(), y0, y1],
               aspect="auto", origin="lower", cmap=cmap, zorder=2)
verts = [(years[0], y0)] + list(zip(years, vals)) + [(years[-1], y0)]
path = Path(verts, [Path.MOVETO] + [Path.LINETO] * (len(verts) - 2) + [Path.CLOSEPOLY])
im.set_clip_path(PathPatch(path, facecolor="none", edgecolor="none",
                           transform=ax.transData))   # ← transform 必须给
```

⚠️ 不给 `transform=ax.transData` 会裁切失效 → 渐变铺满整个坐标轴（变成实心色块）。

## 标注（统一格式 + 细引线）

```python
def tag(i, text, dy, color=MUTED, size=11.5, weight="normal"):
    ax.annotate(text, xy=(years[i], vals[i]), xytext=(0, dy),
                textcoords="offset points", ha="center",
                fontsize=size, color=color, fontweight=weight, zorder=7,
                arrowprops=dict(arrowstyle="-", color=FAINT, lw=0.9,
                                shrinkA=0, shrinkB=5))
tag(0,  f"1960  {vals[0]:.2f}", -34)
tag(pk, f"2021  {vals[pk]:.2f}（峰值）", 30, color=AFTER, size=12.5, weight="bold")
tag(-1, f"2025  {vals[-1]:.2f}", -34)
```

## 内嵌局部放大图（诚实原则的实现手段）

```python
axin = ax.inset_axes([0.075, 0.565, 0.285, 0.315])   # [x, y, w, h] 相对坐标
axin.set_facecolor("#fffdfa")
m = years >= 2016
axin.plot(years[m], vals[m], color=ACCENT, lw=2.2, zorder=3)
axin.scatter(years[m], vals[m], s=16, color=ACCENT, zorder=4)
axin.set_xticks([2016, 2020, 2025])
axin.tick_params(colors=MUTED, labelsize=8.5, length=0)
for s in ("top", "right"):
    axin.spines[s].set_visible(False)
axin.grid(axis="y", color=GRID, lw=0.7)
axin.set_axisbelow(True)
axin.set_title("2021 年后，连续四年回落", fontsize=10, color=AFTER,
               fontweight="bold", pad=6)
```

放**曲线还很低的那一侧**的留白区（本次是左上角，因为 1960–1980 年人口在低位），避免压住主曲线。

## 轴与网格

```python
ax.grid(axis="y", color=GRID, lw=0.9, zorder=0)
ax.set_axisbelow(True)
for s in ("top", "right", "left"):
    ax.spines[s].set_visible(False)
ax.spines["bottom"].set_color("#ddd7cf")
ax.tick_params(axis="both", length=0, colors=MUTED, labelsize=11)
ax.set_yticks([8, 10, 12, 14])
ax.set_yticklabels(["8", "10", "12", "14"], fontsize=9.5, color="#cfc9c0")
ax.set_xticks(list(range(1960, 2021, 10)) + [2025])
```

## 标题 / 来源

```python
ax.text(0, 1.115, "中国人口，1960–2025", transform=ax.transAxes,
        fontsize=25.5, color=INK, fontweight="bold", va="bottom")
ax.text(0, 1.045, "六十年间增长了一倍多，拐点刚刚开始",
        transform=ax.transAxes, fontsize=12.5, color=MUTED, va="bottom")
fig.text(0.055, 0.028,
         f"数据来源：世界银行 World Bank Open Data（SP.POP.TOTL），取数于 {RETRIEVED}",
         fontsize=10, color="#9c968d")
fig.subplots_adjust(left=0.06, right=0.975, top=0.845, bottom=0.135)
fig.savefig(out, facecolor=BG)
```

`RETRIEVED = time.strftime("%Y-%m-%d")`，**动态取，别硬编码**（硬编码会过时，也容易被视觉模型当成笔误）。

## 结构建议

脚本拆成两个函数，便于单独跑和排查：

- `fetch_*()` — 只负责取数（`subprocess` + `curl`），返回 `[(year, value), ...]`，滤掉 null、排序
- `draw(rows, out_path)` — 只负责绘图

模块级放 `INDICATOR` / `COUNTRY` 常量，用户换主题时改一行。
