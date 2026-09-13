# Free 模型横评（2026-09-13 实测）

对 Cline endpoint（`https://api.cline.bot/api/v1`，key 在 `~/.hermes/.env` 的 `CUSTOM_CLINE_API_KEY`）上**全部 19 个 `:free` 模型 + z-ai/glm-5.3-flash** 做了两轮共 4 个任务的实测，用于选复审模型和写作模型。

**实测脚本**（可复用）：`~/.hermes/cache/model_bench.py`（第一轮）、`model_bench2.py`（第二轮）、`model_bench_final.py`（合并打分）。结果 JSON 同目录 `model_bench_results.json` / `model_bench_round2.json` / `model_bench_final.json`。

## 测法

| 任务 | 内容 | 判据 |
|---|---|---|
| A1 挑刺 | 给一篇**植入 7 类 AI 味**的假稿（套话开头/空泛修饰/排比空转/升华结尾/通稿腔/书面词/网感梗），跑复审 prompt | 结论应为「返工」，且引用的原文短句要真实存在 |
| A2 误报测 | 给一篇**真人写的合格稿**（当天已发布、已过复审的微头条） | 结论应为「不返工」。判「返工」= 误报 |
| B1/B2 写作 | 给同一份核实过的素材 + 风格铁律，要求写 400-500 字微头条（两题题材不同） | 字数 400-500、禁用词 0、结尾问句、数字/事实用上 |

## 结论（按可用度）

**复审（挑 AI 味）首选**
1. `cohere/north-mini-code:free` —— 挑刺准、对好文不误报、~10s。**缺点**：爱超长（要求 ≤500 字却输出 724 字），偶发幻觉引用（把不在文里的“可谓”当命中）。
2. `nvidia/nemotron-3-super-120b-a12b:free` —— 两轮都判对（好文“无命中项+不返工”），写作也唯一两题都 400-500 字合规且零禁用词；**缺点**慢（~70s），文风偏说明书。
3. `dots-studio/dots-3-note-preview:free` —— 不误报，但写作超长（513/583 字）。

**写稿首选**
- `google/gemma-4-26b-a4b-it:free` —— 文笔最活、4/4 稳定、~10s；**但**① 事实易串（把旧版“双指按压”混进新指南）② 复审时对好文误报“返工”，别拿它当自己稿子的裁判。
- `nvidia/nemotron-3-super-120b-a12b:free` —— 事实最稳、长度最合规，适合“准确性优先”的题。

**避坑**
- `nvidia/nemotron-3.5-content-safety:free`：输出 15-52 字，基本不干活。
- `nvidia/nemotron-3.5-lightning:free`：单次 90-200s，常超时。
- `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free`：2/4 成功（常 HTTP 500）。
- `z-ai/glm-5.3-flash`：0/4，全部 429 限流。
- `poolside/laguna-s-2.1:free`、`ling-3.0-flash-fin`：写作字数系统性不达标（350-540 字乱跑）。

**踩坑记录**：`nvidia/nemotron-3.5-content-safety`、`glm-5.3-flash` 这类“看起来很强”的名字未必可用；**free 模型必须实跑验证**，且失败模式以 HTTP 500 / 429 / 读超时为主，脚本里重试+换模型是必需的。

## 复现命令

```bash
python3 ~/.hermes/cache/model_bench.py       # 第一轮（约 13 分钟，含慢模型超时）
python3 ~/.hermes/cache/model_bench2.py      # 第二轮
python3 ~/.hermes/cache/model_bench_final.py # 打分表
```

> ⚠️ 样本量小（每模型每任务 1 次），结论是“可用性排序”而非精确分数；换模型/换日期后建议重跑。
