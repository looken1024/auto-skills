---
name: "openclaw-ops-troubleshooting"
description: "OpenClaw/网关运维排错：cron模型超时修复、网关重启致任务被拒、write工具脱敏secret破坏脚本等。"
---

# OpenClaw 运维排错速查

调试 OpenClaw 网关/定时任务/配置的超时、重启、脱敏等常见坑。

## 1. cron 定时任务报 "model idle timeout"（模型超时）

**症状**：`openclaw cron list` 里 Status 显示 `error (Nx)`，`cron show <id>` 的 last error：
> "The model did not produce a response before the model idle timeout. Please try again, or increase `models.providers.<id>.timeoutSeconds` for slow local or self-hosted providers. If `agents.defaults.timeoutSeconds` or a run-specific timeout is lower, raise that ceiling too; provider timeouts cannot extend the whole agent run."

**根因**：模型（尤其重任务里）流式响应停顿超过默认 idle 看门狗窗口；cron 云模型默认窗口较短。

**修复（两个必须一起调，provider 超时被 agents 上限约束）**：
1. `models.providers.<id>.timeoutSeconds` —— 该 provider 的模型请求超时（含 connect/headers/body streaming/total abort）。例：`models.providers.deepseek.timeoutSeconds=1200`。
2. `agents.defaults.timeoutSeconds` —— 整个 agent run 的超时上限；若低于 provider 超时，provider 超时会被压住。例：`agents.defaults.timeoutSeconds=1800`。

修改 `openclaw.json` 后 `openclaw config validate` 校验，再 `openclaw gateway restart` 生效（重启期间有 draining 窗口，见下）。

**验证修复**：
- 先 curl 直测模型可达性（确认非模型本身挂）：`curl https://api.deepseek.com/v1/chat/completions -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" -d '{"model":"<id>","messages":[{"role":"user","content":"hi"}],"max_tokens":10}'`。
- 再 `openclaw cron run <id> --timeout 1800000` 手动触发，观察 cron 从 `error` → `running` 并能**持续运行**（之前秒级失败、修复后能跑几分钟）即证明超时已解除。

## 2. GatewayDrainingError：重启瞬间任务被拒

**症状**：`openclaw cron run <id>` 返回 `{ok:true, enqueued:true}`，但日志里出现：
> `GatewayDrainingError: Gateway is draining for restart; new tasks are not accepted` → "cron: queued manual run background execution failed"

**原因**：`openclaw gateway restart` 有 draining 窗口（默认 300s，用于排空在跑任务），窗口内新任务不被接受。手动触发若恰好撞上重启，会入队成功但后台执行失败。

**处理**：等网关完全就绪（`openclaw gateway status` 显示 `Runtime: running`，无 draining），再重新 `openclaw cron run <id>`。注意 `cron list` 里 Status 可能仍是上次的 error，需看最新 runId 的日志确认是否真正执行。

## 3. write / 脚本里密钥被脱敏成 `***` 破坏代码

**症状**：用 write 工具写的验证脚本（内含从配置读取的 API secret/拼接的 URL），运行时 SyntaxError，例如：
> `f-string: single '}' is not allowed` 直接把 `{secret}` 位置显示成 `***`

**原因**：OpenClaw 的脱敏机制会把脚本里出现的真实密钥值（如拼接进 URL 的 app_secret）替换成 `***`，破坏 f-string/字符串字面量语法。

**处理**：含敏感拼接的临时验证脚本，**别用 write 落盘**，改用 exec 的 heredoc 方式运行（`python3 - <<'PYEOF' ... PYEOF`），或从配置文件按需读取、避免把密钥拼进会被展示/脱敏的字符串字面量。

## 4. 常见排查命令
- `openclaw gateway status` —— 网关运行状态（running / draining / port / dashboard）
- `openclaw gateway restart` —— 重启（比 stop+start 安全，会排空在跑任务）
- `openclaw config validate` —— 校验 openclaw.json 语法
- `openclaw cron list` / `openclaw cron show <id>` —— 定时任务状态与 last error
- `openclaw cron run <id> --timeout <ms>` —— 手动触发一次
- 网关日志：`/tmp/openclaw/openclaw-<YYYY-MM-DD>.log`
