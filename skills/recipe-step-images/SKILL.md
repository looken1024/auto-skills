---
name: recipe-step-images
description: "Use when 给菜谱步骤图统一加文字、排封面或做菜谱图文。脚本化批处理，字号位置一致。"
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [recipe, image, text-layout, pillow, cover]
    category: creative
    related_skills: [douyin-card-pipeline]
---

# 菜谱步骤图加字 + 封面排版

用户给菜谱文字，按步骤顺序发来图片；输出每步一张带字图 + 一张封面。全部用脚本，不手搓。

## When to Use

- 用户发来菜谱和按步骤排列的操作图，要求加统一文字
- 要做菜谱封面（顶部大标题 + 渐变压暗）
- 需要给一批图套完全相同的文字版式（字号、边距、位置固定）

## 环境

- Python 3 + Pillow >= 10（Pillow 可直接 `truetype` 加载 woff2）
- 字体：思源宋体 Bold（Noto Serif SC 700）。首次先跑 `bash scripts/setup_fonts.sh`，下载到 `assets/fonts/`
- 无网络时回退系统 `wqy-zenhei.ttc`（黑体，观感差一档）
- 校验字体是否含标题用字：`fontTools` 读 cmap（见坑）

## 步骤图版式（用户 2026-11 定稿，别随便改）

| 项 | 值 |
|---|---|
| 输出宽度 | 1080，等比缩放不裁剪 |
| 文字位置 | 图片**上方**，距顶 4.5% |
| 左右边距 | 7% |
| 字号 | 宽度 × 4.2%（1080 宽 = 45px） |
| 行距 | 1.45 |
| 底色 | 圆角半透明黑 rgba(0,0,0,150)，白字（样式 A，默认） |
| 样式 B | 白字黑描边无底色，浅底图会糊，仅备选 |

文字超过约 60 字会自动降到 32% 高度以内，字号因此可能变小；要绝对统一就控制文案长度。

## 用法

批量：
```
python3 scripts/recipe_step_text.py --batch steps.json --outdir out --style A
```
`steps.json`：`[{"img":"src/1.jpg","text":"1. 处理菜花：菜花掰成小朵……"}]`

单张：`--img src/1.jpg --text "1. 处理菜花：……" --out out/1.jpg`

封面：
```
python3 scripts/cover_design.py --img cover_src.jpg --title 干锅菜花 \
  --en "DRY POT CAULIFLOWER" --kicker "家常川味 · 2～3人份" --out cover.jpg
```
封面 1080×1440；顶部 46% 黑色渐变（alpha 215→0）；标题 172px、字距 14、轻投影；红色短线 #C63E28；英文 24px、字距 11。

## 工作流（用户逐张发图）

1. 收到菜谱立刻把它拆成 `steps.json`（每步一条：`step` / `img` / `text`），**再等图**。编号先定死，后面收到的图只往上对号，不会错位。
2. 每道菜一个工作目录：`~/recipe_imgs/<拼音菜名>/`，内含 `steps.json`、`src/`（原图）、`out/`（成品）、`cover_src.jpg`、`cover.jpg`、`<菜名>_steps.zip`。不要把所有菜混在同一层。
3. 用户按顺序发图。每收到一张：立刻从微信缓存拷进 `src/N.jpg`（路径形如 `~/.hermes/cache/documents/native-inputs/<hash>/img_*.jpg`，缓存会被清理，别直接拿原路径当输入），用第 N 步文案渲染 `out/N.jpg`，马上回传预览并报“第 N 步好了”。
4. 用户说“这张发错了”时，等新图直接覆盖同名 `src/N.jpg` / `out/N.jpg`，不另起编号。
5. 全部收完：跑 `python3 scripts/verify_outputs.py steps.json out` 校验尺寸与字号，再打包 zip 一起给。
6. 封面：默认等用户发成品图当底图——他明确要求自己提供底图、只要排字，不要主动 AI 生成底图（除非他让你生成）。标题用菜名，英文副标题给意译，kicker 写版本与份量（如“豆角五花肉 · 2～3人份”“家常少油版 · 2～3人份”）。

## 坑

- 步骤编号由文案自带（“1. 处理菜花……”），脚本不会自动加。
- 换字体前用 fontTools 查缺字：`TTFont(p).getBestCmap()`，标题字不在 cmap 里会渲染成空白。
- pollinations 免费通道的 402/503 是限流（1 张/45 秒），不是坏 key：间隔 50 秒重试即可。别加 `?width=` 等参数，容易触发 402；可用入口是 `https://pollinations.ai/p/<urlencoded prompt>`。
- 本机 `vision_analyze` 曾因模型名不匹配报 400，无法自检画面，成图效果交给用户确认。

## 参考

- `scripts/setup_fonts.sh` 下载字体
- `scripts/recipe_step_text.py` 步骤图加字
- `scripts/cover_design.py` 封面排版
- `scripts/verify_outputs.py` 收尾一致性校验（尺寸/字号/缺图）
- `references/layout-spec.md` 版式参数与设计理由
