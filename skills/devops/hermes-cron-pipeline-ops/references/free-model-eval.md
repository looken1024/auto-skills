# 给任务选模型：可复用测法与实测结论（2026-09-13，Cline 免费池 19 个模型 + glm-5.3-flash）

## 为什么要这么测

“哪个模型好”取决于**角色**。给复审选模型，只看“能不能挑出毛病”会选错——**爱乱报错的模型比漏报的更毁流程**。所以每个角色至少两个方向测：

| 任务 | 设计 | 判据 |
|---|---|---|
| A1 挑刺 | 给一篇**植入 7 类已知 AI 味**的假稿（套话开头/空泛修饰/排比空转/升华结尾/通稿腔/书面词/网感梗），跑真实复审 prompt | 结论应“返工”；引用的原句必须真实存在（用引号内容反查原文，抓幻觉引用） |
| A2 **误报测** | 给一篇**真人写的合格稿**（当天已发布、已过复审的成品） | 结论应“不返工”。判“返工”＝误报，直接扣分 |
| B1/B2 写作 | 同素材换两个题，按风格铁律写 400-500 字 | 字数 400-500、禁用词 0、结尾问句、数字/事实用上、**不编造情节** |

补充指标：4 项任务成功率（稳定性）、耗时、是否把工具用全（多步任务要单独探测，见 SKILL.md 第 4 节）。

## 实测结论（本机，2026-09-13）

**复审（挑刺且不误报）**
- `cohere/north-mini-code:free` —— 挑刺准、约 8-10s，但**爱误报**（把好文判返工）、输出超长（要求 ≤500 字却给 700+）、偶发幻觉引用；弱点在多步 agentic 场景（只写一半就交稿）。
- `nvidia/nemotron-3-super-120b-a12b:free` —— 两轮都判对，写作唯一两题都 400-500 字合规、零禁用词零编造；缺点是慢（70-145s）、文风像说明书。
- `dots-studio/dots-3-note-preview:free` —— 不误报、最规整（每步工具都用两次），写作偏长（513/583 字）。

**写作/内容**
- `google/gemma-4-26b-a4b-it:free` —— 文笔最好、约 10s，但**会把两版资料串在一起**（事实串味）；别让它做自己稿子的裁判。

**避坑**
- `nvidia/nemotron-3.5-content-safety:free` 基本不干活（输出十几字）；`nemotron-3.5-lightning:free` 单次 90-200s 常超时；`nemotron-3-nano-omni-30b:free` 常 500；`z-ai/glm-5.3-flash` 全 429。
- 字数系统性不达标：`poolside/laguna-s-2.1:free`、`ling-3.0-flash-fin:free`。
- 会编造情节（禁用）：`inclusionai/ling-3.0-flash-sante:free`（实测给稿子加了“摔杯子/饭都不让吃/眼眶红了”等原文没有的细节）。

## 复现

- 本机脚本：`~/.hermes/cache/model_bench.py`（第一轮）、`model_bench2.py`（误报测+换题）、`model_bench_final.py`（合并打分）
- 明细表：同一目录的 `model_bench_results.json` / `model_bench_round2.json` / `model_bench_final.json`
- 微头条流水线侧的更详细对照：`toutiao-micro-publish/references/free-model-bench.md`

## 使用注意

- 每个模型每项只跑 1 次，结论是**可用性排序**，不是精确分数；换模型/换日期要重跑。
- 免费池会随机 429 → 无论选谁都要配 `fallback_providers` 链（SKILL.md 1.2）。
- 抽样时要看当前可用清单：`curl -s <base>/models` 里筛 `:free`。
