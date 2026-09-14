---
name: "gzh-image-trend-miner"
description: "每日调研公众号热门图片/图集趋势，动态把热门关键词加入 wechat-ai-publisher 图集话题池。"
---

# 公众号热门图片趋势挖掘（gzh-image-trend-miner）

每天调研公众号生态里什么图片/图集内容火（朋友圈刷屏图、公众号封面流行题材、节日/季节热点意象），把有把握的结论转化为 **Pexels 能搜到的实拍关键词**，动态补进图集流水线的话题池，让自动图集蹭上流行趋势。

## 触发场景
- "今天公众号什么图火" / "调研下热门图片趋势"
- "更新下图集关键词" / "往话题池里加几个热门词"
- cron 定时任务（每日上午自动跑一轮）

## 工作流程（4 步）

### Step 1 调研趋势（web_search，多路交叉）

每次至少搜 3 路（结果存档进报告，别只搜一路就下结论）：
1. 节令/节日热点："<当前月份>月份 公众号 封面图 流行"、"<即将到来的节日> 海报 意象"（如中秋→圆月桂花、开学季→校园）
2. 图集/壁纸类热门："公众号 图集 爆款 题材"、"手机壁纸 流行 主题 <月份>月"
3. 视觉设计趋势："平面设计 流行 色彩 <年份>"、"摄影 热门 题材 社交媒体"

判据：一个题材要进入话题池，需要 **≥2 路搜索结果都指向它**，或有明确节令窗口（如中秋前 5 天圆月必然火）。

### Step 2 转化为 Pexels 可搜关键词（硬约束）

- 话题池是给 `pexels_gallery_draft.py` 用的，**每条必须是 Pexels 实拍能搜到的横图场景词**，中英双语 `{"cn":..,"en":..}`
- Pexels 搜不到的（明星肖像、logo、截图类）不许进池；名人/事件类按 expand_topics.py 的先例泛化成场景词（红毯、领奖台）
- 节令词带窗口意识：中秋词只在节前 7 天加、节后主动标记过期

### Step 3 动态加入话题池

写入 `~/.hermes/skills/wechat-ai-publisher/scripts/topics.json`：
- 先读现有池，按 cn 去重，**每次最多加 5 条**（池子膨胀会稀释每话题的轮换周期）
- 加之前备份 topics.json（copy 成 topics.json.bak-<ts>）
- 写回后 `python3 -c "import json;json.load(open(...))"` 验证 JSON 合法
- 节令过期词：在本 skill `references/trends.json` 里记 `{"cn":..,"expires":"YYYY-MM-DD"}`，后续轮次发现过期就从 topics.json 移除

### Step 4 存档报告

报告写本 skill 的 `reports/YYYY-MM-DD.md`：搜了哪几路、发现什么趋势、加了哪几条词（附证据：哪两路搜索指向它）、过期清理了什么。最终回复只给 ≤200 字摘要（引用文件不贴全文——参考 weitoutiao-feedback-optimizer 的输出纪律教训）。

## 调度
- cron：每日上午 09:40（错开其他任务），agent 版，带 continuity（能看到上轮报告和 trends.json，避免重复调研同一结论）
- GitHub 提交：改完主动跑 `bash ~/.hermes/scripts/skills_backup.sh`（topics.json 在 wechat-ai-publisher 下会一起被推）

## 红线
- 不为追热点加 Pexels 搜不到的词——搜不到=图集流水线直接跳题，白占池位
- 每次加词 ≤5 条，宁缺毋滥
- 节令词必须带过期日期，不做永久性节令污染
- 只加实拍授权可用的场景词，不碰肖像/logo/截图
