# Hermes cron 任务模型接线排错（2026-09-13 实战记录）

一次真实的“cron 内容任务不发内容”排错链，按发现顺序记，便于下次 5 分钟内定位。

## 现象

任务每 2 小时一跳，平台上没有任何新内容；`hermes cron list` 里 last_status=error，但错误只有一句。

## 依次排到的四层根因

| # | 症状 | 根因 | 处理 |
|---|---|---|---|
| 1 | `HTTP 400: The supported API model names are deepseek-flash, deepseek-v4-pro, but you passed cohere/...` | 手工 `hermes cron edit --provider custom ...` 用了**不存在的 provider 名**，命令不校验，触发时回落到全局 base_url | 用配置里真实的 provider 名（`hermes config get providers`），pin 完复核落盘值 |
| 2 | `[drift_skip] ... this job is unpinned` | 全局 provider/model 换了，旧任务未 pin | 显式 pin，且 pin 成与当前全局一致的值 |
| 3 | `Invalid API response (retry 1/3): response.choices is None` | **cron 走非流式直连，而上游非流式响应被包成 `{"data":...}`** | 本地解包代理 + provider（见 `scripts/cline_unwrap_proxy.py`） |
| 4 | `HTTP 500 ... from Openrouter: 429` | 免费模型被上游限流（瞬时） | 配 `fallback_providers` 链，自动切下一个免费模型 |

第 3 条的证据链（当时一步步测出来的）：

```
非流式直测上游:      top keys ['data','success'] → 无顶层 choices   ❌ 复现故障
流式直测上游:        data: {"choices":[...]} 标准 SSE            ✅
CLI/网关聊天（走流式）: 正常                                      ✅

→ 结论：上游只在流式下返回标准形状；cron/子代理走非流式，必须过一层解包。
```

## 关键判定命令

```bash
# 日志里看走的是哪条路
grep "OpenAI client created" ~/.hermes/logs/agent.log | tail -5
#   chat_completion_request        → 非流式（cron/子代理）
#   chat_completion_stream_request → 流式（CLI/网关聊天）

# 任务是否真的落盘 pin 了
hermes cron list | grep -A3 <job_id>

# 上游响应形状
curl -s -X POST <base_url>/chat/completions -H "Authorization: Bearer $KEY" -H 'Content-Type: application/json' \
  -d '{"model":"<m>","messages":[{"role":"user","content":"OK"}],"stream":false}' \
  | python3 -c "import json,sys;d=json.load(sys.stdin);print(list(d.keys())[:5], bool(d.get('choices')))"
```

## 部署解包代理（一次性）

1. 放脚本（示例：`~/.hermes/bin/cline_unwrap_proxy.py`，同 `scripts/cline_unwrap_proxy.py`），前台跑一次确认非流式已返回顶层 `choices`。
2. 装 systemd 服务（开机自启 + 崩溃自拉；建议再加一个每 10 分钟的看门狗 cron 兜底：端口没在听就拉起，正常则静默）：

```ini
[Unit]
Description=Upstream unwrap proxy
After=network-online.target
[Service]
User=ubuntu
ExecStart=/usr/bin/python3 /home/ubuntu/.hermes/bin/cline_unwrap_proxy.py --port 8899
Restart=always
[Install]
WantedBy=multi-user.target
```

3. 配 provider：`providers.<名>.base_url = http://127.0.0.1:8899/v1`、`key_env`、`api_mode: chat_completions`，再 `hermes cron edit <id> --provider <名> --model <模型>`。

## 免费模型可用性（2026-09-13 实测，19 个 `:free`）

- **能跑完多步 agentic 流程**（4 步探测：web_search→terminal→read_file→汇总）：`google/gemma-4-26b-a4b-it:free`、`dots-studio/dots-3-note-preview:free`、`nvidia/nemotron-3-super-120b-a12b:free`。
- **单轮文本任务好、撑不住长流程**：`cohere/north-mini-code:free`（审稿挑刺最准、8s；但写稿会超字数，长流程会半途交卷并编造内容）。
- **基本不干活**：`nvidia/nemotron-3.5-content-safety:free`（输出 15-52 字）、`nvidia/nemotron-3.5-lightning:free`（单次 90-200s，常超时）、`nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free`（2/4 成功，常 HTTP 500）、`z-ai/glm-5.3-flash`（4/4 全 429）。
- 通用结论：**`:free` 模型必须实跑验证**，失败模式以 HTTP 500 / 429 / 读超时为主，脚本与任务都需要“重试 + 换模型”。

## 代理/出网的一个测量陷阱

本机 shell 里**全局设了 `http_proxy/https_proxy`（mihomo mixed-port）**。做“直连 vs 代理”对比时，若不察觉，会把两次都走代理的结果误读成“代理无效”。对比前先 `env | grep -i proxy`，或显式 `curl --noproxy '*'`。
（另：mihomo 若未配 `external-controller`，运行时切不了节点；换节点要改配置后重启 mihomo。）

## 任务不改内容也能“看起来成功”的坑

- cron 任务的 last_status=ok 只表示**本轮没有异常退出**，不代表交付完成：实测出现过“状态 ok 但只写了一半就交卷、没发布、没记台账”。
- 因此任务 prompt 必须要求结尾输出 `RESULT: ...` 行，并且**事后到平台后台/台账核实**。

## 日志/证据留存

- 任务输出：`~/.hermes/cron/output/<job_id>/YYYY-MM-DD_HH-MM-SS.md`
- 执行台账：`~/.hermes/cron/executions.db`（`executions` 表：claimed_at/started_at/finished_at/status/error；`cron_incidents` 表：failure_type/state）
- 网关/智能体日志：`~/.hermes/logs/agent.log`（`grep <session_id>` 拉单会话全过程）、`errors.log`
- 会话原文：`~/.hermes/state.db` 的 `messages` 表（按 session_id 查，能看到模型当时的自述与工具返回）
