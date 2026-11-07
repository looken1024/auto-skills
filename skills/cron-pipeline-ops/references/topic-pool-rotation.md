# 图集话题池自动轮换（每 3 天）

## 背景
图集 cron 每小时一条，话题池 `topics.json` 会不断被消耗；台账里累计出图多的话题，Pexels 检索深度被吃穿，继续选只会反复出旧图。2026-10-19 用户要求“把经常出现的剔除掉，换一批新的”，随后要求做成 **每 3 天自动跑一次**。

## 落地方案
- 脚本：`~/.hermes/skills/wechat-ai-publisher/scripts/rotate_topics.py`
- 银行：同目录 `topic_bank.json`（`pending` / `used` / `rejected` 三段）
- 台账：`~/.hermes/skills/wechat-ai-publisher/logs/gallery_sent_md5.json`
- 任务：cron `21a4b0cf5a35`，`every 72h`，deliver=origin

## 轮换规则（默认值）
| 参数 | 默认 | 含义 |
|---|---|---|
| `--remove-top` | 30 | 每轮最多剔除多少条 |
| `--window-days` | 3 | 统计窗口 |
| `--life-max` | 27 | 累计出图达到即算高频 |
| `--min-results` | 12 | Pexels 横图最低产量 |

高频 = 最近 3 天被选中 ≥2 次 **或** 累计出图 ≥27 张；按 (窗口次数, 累计次数) 降序取前 N 条剔除，再**等量**从银行 pending 补入，保持池子规模稳定。

## 新话题验证
每条候选先打 Pexels `search?per_page=24&orientation=landscape`，横图数 ≥12 才入池。成功 → 从 pending 移到 used；失败 → 移到 rejected（记录原因），不再重试。

**Pexels 并发坑**：10 线程并发会大量 `SSL: UNEXPECTED_EOF_WHILE_READING` / `handshake timed out`，看起来像“查询没结果”。**串行 + 25s 超时 + 3 次重试**才稳。

## 银行供血
银行 pending 低于 60 条时，同一个 cron 任务（agent 模式）会：
1. 读 `topics.json` 与 bank，补充 60 条全新自然风景候选（国内景点/山川湖海/花草树木/冰雪沙漠/野生动物，禁建筑/城市/人文/节庆）
2. 不自己调 Pexels，交给脚本下一轮统一验证

## 多池并存（2026-11-03）
同一脚本可读不同池：`GALLERY_TOPICS_FILE=/abs/path/topics_stunning.json`（脚本的 `TOPICS_JSON` 已支持该环境变量）。当前布局：

- 每 2 小时图文 job（`9d58e7843134`，`0 */2 * * *`）→ `topics_stunning.json`（大气/炫酷/不常见风景专池，2026-11-07 起 128 条）
- 每小时贴图 job（`6b86d039a651`）→ `topics.json`（通用池，2026-11-07 起 200 条）

两者的 topic-day 去重共用 `logs/gallery_topic_day.json`，同一天不会重复选同一话题。

## 按主题批量增删
用户会直接点名增删，不要沿用旧口径（“只留自然风景”已被雕塑/海滩/动物/名画多次覆盖）：

- 加：先枚举候选 → Pexels 验证横图 ≥12 → 按 `cn`/`en` 两维去重后写入两个池
- 删：按类别扫 `cn` + 英文 `en` 两维；**`峡湾`(fjord) 不算 `峡谷`**，删除前把边界告诉用户
- 每次都要 `cp topics.json topics.json.bak-<ts>`（两个池都备），并同步清 `topic_bank.json` 的 `pending`，否则轮换会把刚删的词补回来

## 验证
```bash
python3 rotate_topics.py --status                 # 池子/银行余量
python3 rotate_topics.py --remove-top 3 --dry-run # 只算不写
python3 rotate_topics.py --remove-top 3           # 真写，验证备份+银行出队
```
写入前自动备份 `topics.json.bak-<ts>` 与 `topic_bank.json.bak-<ts>`。

## 坑
- **不要复用旧的 `expand_topics.py`**：它的分类候选表里全是历史用过的词，启用等于把刚剔掉的话题原样加回来。
- 台账里的 `topic` 是话题中文名；改名会让历史计数断档，保持 `cn` 稳定。
- 图集脚本里的 `TOPIC_EXHAUSTED=30` 本来就排除 ≥30 张的话题，这些词留在池里只是死重，轮换时优先清掉。
