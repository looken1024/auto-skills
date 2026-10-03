---
name: "hermes-cron-pipeline-ops"
description: "Debug & harden Hermes cron jobs: models, pinning, output."
---

# Hermes 定时任务 / 内容流水线运维

给“跑在 Hermes cron 里的多步内容流水线”做排错与加固：模型链怎么选、任务为什么静默停摆、`ok` 为什么不代表发成功、怎么用最小代价验证一次改动。

**适用**：公众号图集草稿、微头条自动发布、任何 `no_agent`/agentic 定时任务；一次失败 → 连错 N 小时的“静默腐烂”；免费模型池的 429 抖动。

## 0. 先分清两条调用路径（90% 的怪问题在这）

| 场景 | 调用方式 | 端点要求 |
|---|---|---|
| CLI / 网关聊天会话 | **流式**（`chat_completion_stream_request`） | 常规 OpenAI 兼容 |
| **cron 任务 / 委派子代理** | **非流式直连**（`should_use_direct_api_call`，为线程安全设计） | **必须支持非流式返回标准格式** |

日志里一眼区分：`OpenAI client created (chat_completion_request, ...)` = 非流式；`(chat_completion_stream_request, ...)` = 流式。

推论：**“脚本/CLI 能跑，cron 挂”这个组合，优先怀疑非流式差异**，不要再怀疑模型或网络。典型实例（包壳端点）：`references/cline-nonstream-envelope.md`。

## 1. 模型链配置与排错

### 1.1 pin 任务模型
```bash
hermes cron edit <job_id> --provider <provider> --model <model>
```
- **`--provider` 不校验**：写个不存在的名字会被静默接受，任务照跑但**回落到全局 provider**（端点与模型名不匹配 → 例：`HTTP 400: The supported API model names are deepseek-flash, deepseek-v4-pro, but you passed cohere/north-mini-code:free`）。
- 真实 provider 列表：`hermes fallback list` 或 config.yaml 的 `providers:` 段。
- 改完**复核落盘**：`hermes cron list` 或读 `~/.hermes/cron/jobs.json` 的 `provider`/`model`。
- **未 pin 的任务会在全局模型漂移时被 `drift_skip` 静默跳过**（不花钱，但任务停摆）→ 要么 pin 到与全局一致，要么 pin 到一个真实存在的 provider。

### 1.2 免费模型 429 → fallback 链
```bash
hermes config set fallback_providers '[{"provider":"cline_local","model":"dots-studio/dots-3-note-preview:free"}, ...]'
hermes fallback list   # 复核
```
键名 `fallback_providers`（源码 `hermes_cli/fallback_config.py`）；免费池 429 是随机的，配链后单次任务不会整条挂。

### 1.3 按角色选模型（别拍脑袋）
测法（挑刺召回 + **对好文的误报测** + 写作合规）与实测结论：`references/free-model-eval.md`。
一句话结论：**审稿要“能挑刺且不误报”**（弱模型常把好文判返工）；**写稿要长度合规 + 事实不串**；agentic 多步任务要长度合规 + 会持续调工具（不是写两句就交卷）。

### 1.4 辅助模型（识图/vision 等）必须显式钉住（2026-10-03 踩坑）

`auxiliary.vision` 留空（`None`）时，`vision_analyze` 走 `auto` 解析 → 落到**当时配置的默认 provider**。本机曾落到**套餐欠费**的 `custom_cline` 上报 402，症状是一个劲地说“你没有识图能力？”，**看起来像功能缺失，实际是模型接线问题**。

```bash
hermes config set auxiliary.vision.provider deepseek
hermes config set auxiliary.vision.model deepseek-flash
```

改完**立刻用一张已知内容的图验一次**（问“画面里是什么”看答得对不对），别只看配置写进去了。

**排错顺序**：识图报错先怀疑 402/额度/模型名，再怀疑图片路径或工具本身。`auxiliary.*` 这类“空着就接管默认”的配置，出问题第一件事是**显式钉死**，不要靠 auto。

> 📎 需要第二条识图通道（免 API 额度、可交叉验证）时，**DeepSeek 网页版也能上传图片识图**——实测配方与验证记录见 `references/deepseek-web-image-upload.md`。

## 2. 判断“这次到底跑成没跑成”

- `hermes cron list` 的 `last_status: ok` **只说明流程没报错**，不代表业务做成了（实例：微头条任务 ok，实际没发布、没写台账）。
- 三重校对：
  1. 回执原文 `~/.hermes/cron/output/<job_id>/<时间>.md`（看模型最终说了什么）
  2. `~/.hermes/cron/executions.db`（`claimed_at/started_at/finished_at/status/error`）
  3. **实际产物**：业务侧的台账/列表页（例：`logs/published.log`、头条作品管理页、草稿箱 batchget）
- **最快健康度信号：回执的最后一句**。是结果（`RESULT: 已发布 ...`）才算跑完；是进度说明（“P1-P4 已写入，继续写入 P5-P7”）= 模型半途交卷。

## 3. 加固 agentic 流水线的 prompt（弱模型/长流程必做）

1. **禁止半途交卷**：写明“不得把下一步计划/进度说明当最终回复；做完并校验后才能结束”。
2. **机器可读收尾行**：`最后一行必须是 RESULT: 已发布 <标题>` / `RESULT: 未发布 <卡在哪一步+报错原文>` —— 让排错不用翻日志。
3. **不可重复的副作用要写“只做一次”**：发布/发送/写台账这类动作，明确“确认成功后立即停止，禁止重复点击/重发”（实例：同题重发 3 条，事后手动删 2 条）。
4. **填任何可变 UI 状态前先清空**：表单/编辑器会残留上一次会话内容，先清空再填、并回读校验（否则拼成两篇）。
5. **禁用脆弱的 shell 拼接**：cron 会话里用 heredoc 写 JS/脚本常被截断（`here-document ... delimited by end-of-file`），改成用宿主工具（`browser_exec` 之类）逐段调用。
6. **给回查留迹**：要求把关键中间产物写到固定路径（文案 txt、日志），失败时能接着改而不是重头再来。

## 4. 改完必须验：临时探测任务（不碰生产副作用）

不要拿生产任务直接试发布。用**一次性的探测任务**验真路径：
```bash
hermes cron create "in 6h" "只回复四个字：PROBE-OK" --name "临时探测" --deliver local --provider <p> --model <m>
hermes cron run <id>        # 立刻跑一次
# 读 ~/.hermes/cron/output/<id>/*.md 确认；验完： hermes cron remove <id>
```
要验“多步 + 工具调用”能力，就把 prompt 换成 4 步任务（web_search → terminal → read_file → 汇总），看它是否**全部走完**。

## 5. 站点访问排错：Cloudflare 403

- 400/403 + `<title>Just a moment...</title>`（中文：`正在进行安全验证`）= Cloudflare 人机挑战，**不是网络不通**（DNS/TLS 已通）。API 子域同样会被挑战。
- 看出口 IP：`curl -s https://api.ipify.org`（有代理时加 `--proxy http://127.0.0.1:9981` 对比）。直连与代理出口都是机房 IP 时，这类站点基本用不了——**别在挑战页耗时间，去找替代方案**。
- 无头浏览器不是解法：headless 特征会被识别；靠注入抹 `navigator.webdriver` + 伪装 UA 只是**偶尔**能过，不稳定，不能写进流程。
- **有头浏览器也不是解法（2026-09-13 实测）**：`Xvfb :77` + 非 headless Chrome（真实 UA）同样卡在挑战页 36s 不通过 → 判定这是**出口 IP 信誉**问题，不是浏览器特征问题，别再在浏览器上折腾。
- ⚠️ **测出口 IP 前先看 shell 的代理环境变量（我因此误判过一次）**：本机全局设了 `http_proxy/https_proxy=http://127.0.0.1:9981`，所以“直连”其实**也在走代理**——不用 `curl --noproxy '*'` 的直连/代理对比是无效的，会得出“代理没用”的错误结论。
- 本机 mihomo（`/etc/mihomo/config.yaml`，mixed-port 9981，mode rule）**没开 external-controller**：运行时切不了节点（要改配置重启）；节点基本都是机房 IP（华为云/腾讯云段），对 Cloudflare 也不管用。测节点是否活：python socket 连 `proxies[].server:port` 即可。
- 交付口径：给出“能用的替代”并**先跑通再答复**（例：免 key 出图 `https://image.pollinations.ai/prompt/<urlencoded>?width=512&height=512`，实测 3.7s 返回真实 JPEG；出图后照 `wechat-ai-publisher` 的规矩用视觉模型验一遍）。**完整用法/参数/验图步骤/被墙站点清单：`references/free-image-gen.md`。**

## 5b. 浏览器看门狗 + Cookie 注入（headless Chrome 的静默死亡）

脚本化流水线依赖长期存活的 headless Chrome（9222 端口，`--user-data-dir=/tmp/chrome-wx`）。
**Chrome 会在夜间静默死亡**（无报错、9222 消失），流水线第 1 步连不上 → 整班失败 → 下一班照旧失败 → **连挂 N 小时的静默腐烂**（实测连挂 5 班）。

**排错铁律**：流水线连续失败时，**先查基础设施依赖**（浏览器、代理、daemon），再查模型/业务逻辑。不要看到 `Connection refused` 就去修脚本——脚本没错，是依赖死了。

**修法**：流水线脚本最开头探 9222，挂了就按原参数自动拉起（最多等 30s），拉不起来才发邮件告警。`--user-data-dir` 必须用同一个目录，登录态都在里面。

Chrome 重启后 `/tmp/chrome-wx` 里的 cookie **可能还在也可能过期**，不能假设「目录在 = 登录态在」。用 `scripts/inject_toutiao_cookie.py`（CDP `Network.setCookie` 注入存好的 `sessionid`/`sessionid_ss` → 导航到发布页 → 检查 URL 没跳登录页 + `.ProseMirror` 编辑器就绪）验证。

**完整细节：`references/browser-watchdog-and-cookie-injection.md`。**

## 5c. 小内存机器：OOM Killer 的静默症状（2026-10-01 踩坑）

本机只有 ~1.9G RAM + 2G swap。图片处理类流水线（如图集脚本的 `process_image`）只要对**整图**做 numpy 运算，就会被 OOM Killer 干掉。

- **症状很有误导性**：进程 `exit -9`、**没有任何 Python traceback**，日志里看着像“跑着跑着自己退了”。别先查逻辑，先算内存。
- **改法**：把整图的 float64 运算改 **float32 + 分行块**处理（实测单张峰值 500MB+ → ~150MB）。
- **确认手法**：跑前 `free -m`；事后 `dmesg | grep -i "killed process"` 确认是 OOM 而非别的。
- **Chrome 标签是隐形内存黑洞**：长期存活的 headless Chrome 会堆标签（曾到 27 个，内存 260MB→672MB）。`curl 127.0.0.1:9222/json/list` 列表，`curl 127.0.0.1:9222/json/close/<targetId>` 逐个关。
- 通用经验：**“整图/整文件一次性运算”的写法在这台机器上先想峰值内存**，宁可分块。

## 6. 与其它 skill 的关系

- 微信侧发布细节（压图、素材库、草稿校验）：`wechat-ai-publisher`
- 微头条流水线步骤与风格铁律：`toutiao-micro-publish`（其 `references/free-model-bench.md` 是模型实测明细）
- 本 skill 只管“cron/模型链/任务健康度”这一层，不重复业务步骤。

> 注：`openclaw-ops-troubleshooting` 覆盖同类网关/cron 排错，但本机是 Hermes，第 5 节那些坑它没有；两者可考虑合并（需用户 `hermes curator adopt` 后才能自动改）。

> ⚠️ **2026-10-03：`wechat-ai-publisher`、`toutiao-micro-publish`、`bar-chart-video` 都是用户自有 skill（`created_by=None`），后台 curator 写入会被拒。**
> 涉及它们的新知识（公众号图集 OOM、微头条流水线变更、数据可视化）先落在本 skill 或 `data-chart-scripting` 里，并提醒用户 `hermes curator adopt <name>` 后再回填。
