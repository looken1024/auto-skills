---
name: cron-pipeline-ops
description: "Use when cron 内容流水线模型接线或发布自动化报错、要加固。"
---

# 定时任务型内容流水线的运维（模型接线 · 发布自动化 · 排错）

面向“cron 定时跑一条内容流水线（写稿→复审→浏览器发布→记录）”这类任务的运维与排错。
沉淀自 2026-09-13 一次完整实战：微头条 cron 任务连续失败 → 逐层定位到 provider 名写错、模型漂移、上游响应包壳、免费模型限流与能力不足，并全部修复。

## 何时用
- cron 任务 `last_status=error` / 平台上看不到新内容 / “该发的东西没发出去”
- 报 `Invalid API response ... choices is None`、`HTTP 400 ... model names are ...`、`429`、`drift_skip`
- 要给 cron 任务换模型 / 换 provider / 配 fallback 链
- 任务“跑完了但没交付”（半途交卷、重复发布、内容残留）

## 排错顺序（照这个走最快）

1. **先看任务真实状态与错误原文**（`hermes cron list` / `~/.hermes/cron/output/<job_id>/*.md` / `~/.hermes/cron/executions.db`），别凭平台页面现象猜。
2. **分辨模型调用走的是哪条路**：`grep "OpenAI client created" ~/.hermes/logs/agent.log | tail`
   - `chat_completion_request` = **非流式**（cron / 子代理走这条）
   - `chat_completion_stream_request` = 流式（CLI / 网关聊天）
   → 同模型在聊天里正常、在 cron 里报 `choices is None`，基本就是“上游只在流式下返回标准格式”，见下。
3. **响应包壳**：上游把响应包成 `{"data": {...}, "success": true}`（顶层无 `choices`），而 cron 走非流式 → 用本地解包代理 + 自定义 provider（`scripts/cline_unwrap_proxy.py`；安装与 provider 配置见 `references/hermes-cron-model-ops.md`）。
4. **provider 名 / pin 是否正确**：`hermes cron edit --provider <名>` **不校验 provider 名**，写错的会被静默接受并在触发时回落到全局 provider（→ 上游 400）。pin 完必须复核落盘值（`hermes cron list` 或 `~/.hermes/cron/jobs.json`）。
5. **模型漂移**：全局 provider/model 改过后，未 pin 的旧任务会被 `drift_skip` 保护性跳过。显式 pin，**首选 pin 成与当前全局一致的值**。
6. **限流**：免费模型 `429` 很常见 → 配 `fallback_providers` 链（`hermes config set fallback_providers '<JSON数组>'`，元素 `{provider, model}`），主模型失败自动下切。
7. **模型能力**：链路通了不等于任务能完成，弱模型会半途交卷/编造内容（见下）。

详细命令与实测数据：`references/hermes-cron-model-ops.md`。

## 验证配方（都不产生副作用）

```bash
# ① provider + 模型 + key 是否可用
hermes -z "只回复两个字：正常" --provider <p> -m <m> -t ""

# ② 验证 cron 路径（非流式）而不发真内容：临时任务 + deliver=local
hermes cron create "in 6h" "只回复 PROBE-OK，不要调用任何工具" --deliver local --provider <p> --model <m>
hermes cron run <临时任务id>        # 结果看 ~/.hermes/cron/output/<id>/*.md
hermes cron remove <临时任务id>     # 验完删掉

# ③ 上游响应形状（判断是否包壳）
curl -s -X POST <base_url>/chat/completions -H "Authorization: Bearer $KEY" -H 'Content-Type: application/json' \
  -d '{"model":"<m>","messages":[{"role":"user","content":"OK"}],"stream":false}' \
  | python3 -c "import json,sys;d=json.load(sys.stdin);print(list(d.keys())[:5], bool(d.get('choices')))"
```

**铁律**：任务自己的回执是**自报**，不等于事实。发布/写入类副作用必须回到外部世界核实（平台后台列表、落盘文件、实际内容）。

## 弱模型驱动多步任务：两个典型症状与对策

| 症状 | 现象 | 对策 |
|---|---|---|
| 半途交卷 | 把“下一步计划”当最终回复（如“P1-P4 已写入，继续写入 P5-P7”就结束） | prompt 硬性加：**禁止把进度说明当最终回复**；成功后才能结束；最后一行必须是 `RESULT: 已完成 <结果>` / `RESULT: 未完成 <卡在哪+报错原文>` |
| 能力不足 | 能调工具但撑不住长流程，中途编造内容 | 换能跑完流程的模型；上线前用“4 步探测”（web_search→terminal→read_file→汇总）筛一遍候选模型 |

选型参考（2026-09-13 实测 19 个 `:free`）：能跑完多步流程的 `google/gemma-4-26b-a4b-it` / `dots-studio/dots-3-note-preview` / `nvidia/nemotron-3-super-120b-a12b`；单轮文本强但撑不住长流程的 `cohere/north-mini-code:free`；基本不干活的 `nvidia/nemotron-3.5-content-safety`（输出 15-52 字）、`nvidia/nemotron-3.5-lightning`（单次 90-200s 必超时）、`z-ai/glm-5.3-flash`（全 429）。**`:free` 必须实跑验证，别信名字。**

## 浏览器发布类步骤的硬规矩

1. **调度会话里禁止手写 heredoc 跑浏览器脚本**：heredoc 会被截断（`here-document ... delimited by end-of-file`），脚本只跑一半。改用现成的浏览器工具（如 `browser_exec`，含 `goto_url / wait_for_load / js / cdp / click_at_xy`）。
2. **填内容前先清空编辑器**：残留内容会与本次拼接成“两篇”，字数翻倍。`Ctrl+A` + `Backspace`，回读确认后再填。
3. **不可逆动作只做一次**：发布/提交按钮重复点会重复发布（实测同题发了 3 条，事后手动删 2 条）。
4. **React 下拉菜单要用真实鼠标事件**：`element.click()` 不一定开菜单，用 `cdp('Input.dispatchMouseEvent', type='mousePressed'/'mouseReleased')`。
5. **登录态会过期**，且多个平台可能共用同一个浏览器 profile（cookie 按域隔离）；发布前先确认页面不是登录页。

## 外部模型复盘（把交付物喂给另一个模型挑刺）

任务自己能过审，不等于内容/结果没毛病。把当天产出整批喂给外部模型（网页端开“深度思考”+联网搜索）复盘，常能挖出自己脚本抓不到的问题（事实口径、重复套路、结构同质化）。
登录、发送、抓回复的具体操作与坑（图形验证码、短信延迟、虚拟渲染抓不到文本）见 `references/web-chat-automation.md`。

## 代理/出网的测量陷阱

做“直连 vs 代理”对比前先 `env | grep -i proxy`：本机 shell 全局设了 `http_proxy/https_proxy`（mihomo mixed-port），否则会把两次都走代理的结果误读成“代理无效”。要真直连就 `curl --noproxy '*'`。

## 发布前事实/口径门禁（内容类流水线）

发布类任务的最后一道闸门：复审脚本只抓「AI 味」，**抓不出事实错误**。实测一次外部复盘就从当天 5 条里找出 5 处事实/口径问题（数据口径写错、统计数字论证方向反了、二手名次当事实、自建估算未标注、选择性引用）。完整六条门禁 + 同日多条的结尾/情绪/结构配额 + 复盘 prompt 模板见 `references/pre-publish-fact-gate.md`；可把它当作发布前的 checklist 跑一遍。

## 支持文件
- `references/hermes-cron-model-ops.md` — 四层根因实战记录、判定命令、日志/证据位置、免费模型实测表
- `references/web-chat-automation.md` — 用 browser_exec 驱动网页版大模型（登录/验证码/发送/抓回复）
- `references/pre-publish-fact-gate.md` — 发布前事实/口径六条门禁、同日多条配额、外部复盘 prompt 模板
- `scripts/cline_unwrap_proxy.py` — 响应包壳解包代理（本地 OpenAI 兼容 shim，可 systemd 常驻）
