# Cline 端点非流式包壳 → cron / 子代理模型调用全挂（2026-09-13 实录）

## 现象

- 微头条 cron 任务连败多次：从 `HTTP 400` 到 `Invalid API response after 3 retries: response time 34.5s`。
- 真因那行日志：`agent.conversation_loop: Invalid API response (retry 1/3): response.choices is None | Provider: Unknown` → 三次重试后放弃。
- 决定性对比：**同一 provider/model（`custom_cline-2` + `cohere/north-mini-code:free`）在 `hermes -z "..."` CLI 里正常，在 cron 里必挂**。

## 根因链

1. `api.cline.bot/api/v1/chat/completions` 在 `stream:false` 下返回 `{"data": {choices, ...}, "success": true}`；`stream:true` 才返回标准 SSE。
2. Hermes 的 **cron 平台与委派子代理走非流式直连**（`agent/chat_completion_helpers.py: should_use_direct_api_call()`；测试文件 `tests/cron/test_cron_direct_api_call_62151.py` 明写 `platform="cron"` → True）。
3. 客户端读顶层 `choices` → None → 重试三次失败。

## 已排除的死路（别再试）

- 换路径：`/v1/...`、`/api/v1/openai/chat/completions`、`/openai/v1/chat/completions`、`/api/chat/completions` 全 404；只有 `/api/v1/chat/completions` 可用且包壳。
- 换 key（`CUSTOM_CLINE_API_KEY` / `CUSTOM_CLINE_2_API_KEY`）：两个都包壳。
- `hermes config set streaming.enabled true`：那是 CLI 显示项（`cli.py` 读 `CLI_CONFIG["display"]["streaming"]`），与 API 请求无关。
- 改 api_mode/protocol：provider profile 内没有“解包”开关。
- 注意 Python 里手写的调用不受影响（自己 `d.get("data", d)` 包一层就行）——**“脚本能跑、cron 挂”正是本坑签名**。

## 修复：本地解包代理 + 专用 provider

1. `~/.hermes/bin/cline_unwrap_proxy.py`（stdlib `ThreadingHTTPServer`，`127.0.0.1:8899`）：
   - 路径映射 `http://127.0.0.1:8899/v1/chat/completions` → `https://api.cline.bot/api/v1/chat/completions`；
   - 响应 `{"data": {...}}` 且 data 有 `choices` → 解包为顶层 OpenAI 形状；`/models` → `{"object":"list","data":[...]}`；SSE 原样透传；
   - 无 `Authorization` 时从 `~/.hermes/.env` 读 key。
2. systemd 服务 `/etc/systemd/system/cline-unwrap-proxy.service`（`enable --now`，`Restart=always`）+ Hermes 看门狗 cron（`~/.hermes/scripts/cline_proxy_watchdog.sh`，每 10 分钟 `no_agent`，正常静默）。
3. `config.yaml`：
   ```yaml
   providers:
     cline_local:
       base_url: http://127.0.0.1:8899/v1
       key_env: CUSTOM_CLINE_API_KEY
       api_mode: chat_completions
       model: cohere/north-mini-code:free
   ```
4. 业务任务 pin：`hermes cron edit <job_id> --provider cline_local --model <m>`。

## 验证（三步都过才算好）

```bash
ss -ltn | grep 8899                                   # 1) 代理在跑
curl -s http://127.0.0.1:8899/v1/chat/completions \   # 2) 非流式有顶层 choices
  -H "Authorization: Bearer $K" -H "Content-Type: application/json" \
  -d '{"model":"cohere/north-mini-code:free","messages":[{"role":"user","content":"OK"}],"stream":false}' \
  | python3 -c "import json,sys;d=json.load(sys.stdin);print('choices:',bool(d.get('choices')))"
```
3) 用临时探测任务验 cron 真路径（见 SKILL.md 第 4 节），**不要拿生产任务试发布**。

> 带工具也要验一次：非流式 + `tools` 时 `finish_reason=tool_calls`、`message.tool_calls` 非空，证明解包没把工具调用弄丢。
