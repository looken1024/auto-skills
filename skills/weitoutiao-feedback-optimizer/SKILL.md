---
name: "weitoutiao-feedback-optimizer"
description: "微头条发布后数据分析与自迭代：抓真实展现/点赞数据，总结写作经验并反哺 toutiao-micro-publish。"
---

# 微头条反馈数据分析与自迭代（weitoutiao-feedback-optimizer）

基于「棱镜折射」账号在头条创作后台的**真实用户响应数据**（展现/阅读/点赞/评论），定期分析哪些写法有效、哪些无效，把结论固化成写作规则并反哺 `toutiao-micro-publish` 流水线，形成数据驱动的自迭代闭环。

## 触发场景
- "分析下微头条数据" / "微头条最近表现怎么样"
- "复盘下微头条写作" / "结合数据优化微头条 skill"
- cron 定时任务（每日 21:30 自动跑一轮）

## 闭环流程（5 步）

### Step 1 抓取真实数据（脚本 · 硬性，不许凭印象）

```bash
python3 ~/.hermes/skills/weitoutiao-feedback-optimizer/scripts/fetch_stats.py
```

- 走裸 CDP（websocket-client，`suppress_origin=True`，9222 端口 headless Chrome，profile `/tmp/chrome-wx`），复用已登录的 mp.toutiao.com 会话
- 导航到作品管理页 `https://mp.toutiao.com/profile_v4/weitoutiao`，按 `\n展开\n` 分割每条作品，正则提取 `展现 N阅读 N点赞 N评论 N` + 发布时间 + 正文首行
- 原始数据追加写入本 skill 的 `data/stats.jsonl`（一行一条，带抓取时间戳）
- **前置**：Chrome 必须在 9222 且 mp.toutiao.com 登录态有效；未登录 → 退出码 2，走邮件通知（复用 toutiao-micro-publish/scripts/notify_email.py）
- **踩坑（2026-09-14 实测）**：① `browser-harness` 的 `js()` 助手连不上 9222（Chrome 未带 `--remote-allow-origins`），必须裸 websocket + `suppress_origin=True`；② 列表页需等 8 秒渲染；③ 只信任 `innerText` 解析，不要猜 DOM 结构

### Step 2 数据分析（LLM · 结合数据说话）

读取 `data/stats.jsonl` 近 7 天 + 对照 `~/.hermes/logs/published.log` 台账（知道每条是什么题、几点发的），按维度对比：

1. **展现量分层**：高（>500）/ 中（100-500）/ 低（<100），找高分条目和低分条目的共性
2. **首句类型归因**（核心维度）：首句是「具体事件+数字/人物」还是「泛议题/普遍感受」开头——2026-09-14 首次分析已验证：故事型首句展现 800-1659，议题型只有 26-86，差一个量级
3. **选题类型**：民生议题类（油价/涨工资/政策）vs 具体事件类（当事人/金额/判决），各自平均展现
4. **发布时段**：白天时段（13-20 点）与凌晨（0-3 点）的展现差异
5. **点赞率**（点赞/展现）：题材情绪共鸣度

### Step 3 总结经验（输出报告）

报告写入本 skill 的 `reports/YYYY-MM-DD.md`，结构固定：
1. 数据总览（近 7 天各条：时间 | 题目 | 展现/赞）
2. Top3 与 Bottom3 及归因（写法差异，不是运气）
3. 提炼成 **可执行的写作规则**（每条规则 = 触发条件 + 具体做法 + 支撑数据），不写空话
4. 与现有规则（`references/writing_rules.md`）的 diff：哪些验证了、哪些要改、哪些新增

### Step 4 自迭代 toutiao-micro-publish（硬性 · 有变化才动）

- 分析结论若推翻/补充了现有写作规则 → **用 patch 精准修改** `~/.hermes/skills/toutiao-micro-publish/SKILL.md` 的 Step 2（选题）或 Step 4（写作）小节，改动处标注 `（数据迭代 YYYY-MM-DD）`
- 同步更新本 skill 的 `references/writing_rules.md`（当前生效规则全集 + 每条的支撑数据摘要）
- 修改后 `grep` 自检改动落盘；一条规则连续两轮数据反驳 → 删除并记录原因
- **红线**：只优化写法/选题规则，不改复审闭环、查重铁律、发布安全限制（这些是事故教训，不是数据能推翻的）

### Step 5 存档 + 自动提交 GitHub（硬性）

- 全部产物落在本 skill 目录内：`data/`（原始数据）、`reports/`（分析报告）、`references/writing_rules.md`（规则快照）
- **不建 `logs/` 目录**——skills_backup.sh 的 rsync 排除规则会跳过名为 logs 的目录，数据会丢
- 提交 GitHub 靠已有的每小时 cron `35b448f732e9`（`skills_backup.sh` → github.com/looken1024/auto-skills，SSH key 推送），本 skill 建好后**自动包含**，无需额外任务；但分析 cron 跑完后可主动 `bash ~/.hermes/scripts/skills_backup.sh` 立即推一次

## 调度
- cron：每日 21:30，agent 版（需要 LLM 分析与 patch 修改，不能 no_agent）
- 每轮分析上下文：stats.jsonl 近 7 天 + writing_rules.md + 最近 2 份报告（continuity），足够且不超载
- **输出纪律（2026-09-14 首跑事故，硬性）**：报告正文/数据表/规则全文一律写入文件，最终回复只给 ≤300 字摘要。首跑因把报告全文贴进最终回复，输出超长被截断（`Response truncated due to output length limit`），整轮判 FAILED——数据再准也白跑。

## 红线
- 只用后台真实数据，不编造/估算数据
- 单日数据量小（≤10 条）不下强结论，标注「样本不足，观察中」
- 不为数据好看走极端标题党——规则必须同时过 toutiao-micro-publish 的 AI 味复审
