# “任务成功但零交付”：空转 → 垃圾回复的日志级排查

场景（2026-09-13 实测）：cron 微头条任务 23:00 那班，`last_status=ok`、日志写 “completed successfully”，但平台上看不到任何新内容，用户直接问“这个小时的任务没执行吗”。

## 1. 先纠正两个时间语义（最容易误判）

- `~/.hermes/cron/output/<job_id>/<YYYY-MM-DD_HH-MM-SS>.md` 文件名里的时间戳是**这班的开始时间**，文件是在**结束时**才写下的。
- 任务字段 `last_run_at` 是**结束时间**。
- 所以「文件名 23:23、last_run_at 23:23、下一班 next_run_at 00:00」这种组合并不说明 23:00 没跑；要确认就从文件名反推会话 id 去翻日志（下节）。

## 2. 反推会话 id 并看模型分布

cron 会话 id 命名规则：`cron_<job_id>_<YYYYMMDD_HHMMSS>`（时间戳 = 这班的开始时刻，与输出文件名一致）。

```bash
# ① 最近几班的输出文件（时间 = 开始时刻）
ls -t ~/.hermes/cron/output/<job_id>/ | head

# ② 该班日志尾部（工具调用、API 调用都在这）
awk '/cron_<job_id>_<YYYYMMDD_HHMMSS>/' ~/.hermes/logs/agent.log | tail -30

# ③ 模型分布：是否被 fallback 换掉、换成了谁（主模型 429 会静默下切）
grep "cron_<job_id>_<ts>" ~/.hermes/logs/agent.log | grep -oE "model=[a-zA-Z0-9./:_-]+" | sort | uniq -c | sort -rn

# ④ 结局：api_calls / tool_turns 高而 response_len 极小 = 空转后吐垃圾
grep "cron_<job_id>_<ts>" ~/.hermes/logs/agent.log | grep "Turn ended"

# ⑤ 429 原文（含 quotaMetric / limit / model / retryDelay，直接指出是哪个上游什么配额）
grep "cron_<job_id>_<ts>" ~/.hermes/logs/agent.log | grep -oE "429[^\"]{0,200}" | head
```

实测数据：`api_calls=72/500`、`tool_turns=63`、`response_len=32`，模型分布 `nemotron-3-super-120b:free ×75 / dots-3-note-preview:free ×34 / gemma-4-26b-a4b-it:free ×13` —— 典型“主模型被限流 → 下切到弱 agent → 反复跑同一个脚本空转 23 分钟 → 最后吐 32 字符碎片”。

## 3. 判定表

| 现象 | 结论 |
|---|---|
| 同一个脚本/文件被反复读写，工具返回内容雷同（如恒为 322 字符的 trivial 回显） | 空转 |
| `response_len` < 100 且 `api_calls` > 30 | 空转后吐垃圾，本班零交付 |
| 模型分布里出现 fallback 链上的弱模型且占多数 | 主模型被限流，根因在上游配额 |
| 429 原文里 `limit: 16000`、`model: gemma-4-26b` 反复出现 | 结构性不可用，重试无用 → 换主模型 |

## 4. prompt 层加固（三条，缺一不可）

1. **禁止空转**：连续 2 次工具调用没有产生新信息（同一脚本反复跑、同一页面反复回读、反复重写同一份文件）→ 立刻停止修补，改走最小路径（核心产出 → 复核一次 → 直接交付）。
2. **限时收尾**：全程目标 N 分钟内完成；超过上限仍未交付，就老实输出 `RESULT: 未完成 <卡在哪一步+报错原文>` 然后结束（宁可不发，也不空转到下一班撞车）。
3. **禁止垃圾回复**：任何情况下都不允许把乱码、残句、半截片段当最终回复；最终回复必须包含规定的 `RESULT:` 行。

补充：`last_status` 只反映进程是否正常退出，**不代表交付成功**。对外部世界有副作用的班次，收尾一定要回平台列表/落盘文件核实（本轮就是靠台账最后一条停在 22:17 才确认“这一班确实没发出去”）。
