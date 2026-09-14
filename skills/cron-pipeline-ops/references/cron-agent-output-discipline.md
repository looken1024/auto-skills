# Agent 版 cron 任务的输出纪律（超长回复被截断 → 整轮判 FAILED）

> 沉淀自 2026-09-14 微头条反馈分析任务首跑事故（job 15c63b0007a2）。

## 事故实录

- 任务：每日分析头条后台数据、写报告、patch 优化写作规则、推 GitHub。
- 结果：`RuntimeError: Response truncated due to output length limit`，整轮判 FAILED。
- 根因：**不是工具/数据问题**（stats.jsonl 抓取成功、报告落盘完好），而是 agent 把报告全文贴在最终回复里，撞输出长度上限被截断。
- 讽刺点：数据全对、文件全落了盘，只因回复格式就整轮算失败。

## 硬性纪律（写进 agent 版 cron prompt）

1. **所有报告正文、数据表、规则全文一律写入文件**（reports/、references/ 等），最终回复只给 ≤200-300 字摘要（要点式：做了什么、关键数字一两个、下一步）。
2. 禁止在最终回复里粘贴：报告全文、词条清单全文、日志大段、表格全量。
3. 若本轮结论与上轮无差异、无新产出 → 回复 `[SILENT]`（系统不投递），避免刷屏。
4. 这条纪律要**同步写进对应 skill 的 SKILL.md**（不只靠 prompt），防止将来改 prompt 时弄丢。

## 为什么 prompt 和 skill 都要写

prompt 会随任务重建/覆盖；skill 是持久的。事故后修 prompt 时，把教训同时 patch 进 skill 的调度说明（用「事故日期 + 现象 + 规则」格式），future session 加载 skill 时就自带这条约束。
