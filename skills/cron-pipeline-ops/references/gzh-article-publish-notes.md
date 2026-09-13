# 公众号文章流水线：写作 skill 接线 + 发布自检（2026-09-13 一次完整实战）

用户说“用 gzh 给我写一篇文章放草稿箱”时的落地路径与坑。

## 1. 写作 skill 的真实名字（重要：有悬空引用）

发布 skill `wechat-ai-publisher` 的 Step 2 写的是「通用版 `wechat-article-writer` / 人设版 `laoluo-article-writer`」——**本机不存在这两个 skill**，照抄会找不到。实际能用的：

| 题材 | 用哪个 |
|---|---|
| 通用爆款（民生/职场/情绪） | `gzh-viral-writer`（选题情绪赛道、标题公式、观点文结构、去 AI 味清单） |
| 新闻社会类 | `news-social-writing`（文末必带来源、封面模板、标题三候选） |
| 历史类 | `history-social-writing`（文末强制参考资料） |

`wechat-ai-publisher` 属 **user-owned**（未 curator 化），自主 curation 写不进去；要自动维护它先 `hermes curator adopt wechat-ai-publisher`。本文件就是那些改动临时落在此处的原因。

## 2. 一次成功的六步实录（命令级）

1. **选题先查重**：看 `wechat-ai-publisher/articles/published/` 最近归档（历史号题材集中时尤其必要）。
2. **核事实**：把要写进正文的每个数字/法规/日期都搜一遍（本次核了：1995-03-25 国务院令、1995-05-01 施行、每周 40 小时、企业最迟 1997-05-01、“每周至少休息一日”、加班 1.5/2/3 倍、月计薪 21.75 天）。
3. **写正文 Markdown**（`/tmp/gzh_article.md`）：观点文 `## 01/02/03` 小标题 + 结尾；目标 2000-2600 字（初稿常见只有 1400-1800，要主动补案例/测算）；正文图用 `![说明](/tmp/xxx.jpg)`（**禁 `file://` 前缀**）。
4. **配图**：封面按 2.35:1（940×400）裁；正文图宁缺毋滥（本次 1 张）。素材与验证见 `references/image-sources.md`。
5. **发布**：
   ```bash
   cd ~/.hermes/skills/wechat-ai-publisher && python3 scripts/run_pipeline.py \
     --article /tmp/gzh_article.md --cover /tmp/gzh_cover.jpg --body-images /tmp/gzh_body.jpg \
     --title "<标题>" --author "棱镜折射" --digest "<≤50字摘要>" --theme orange
   ```
   `--body-images` 逗号分隔可传多张；主题 `default/green/purple/orange/cyan`（无 brown）；默认仅存草稿，不群发。
6. **回验 + 归档**：`draft/batchget` 拉回草稿，**字节级解码**（`.decode('utf-8')`）看中文；归档在 `<skill>/articles/published/<日期>_<标题>.md` + `_meta.json`。

## 3. 发布后 HTML 自检（一条命令判掉全部已知坑）

从 batchget 的 `content` 统计标签数量：

| 标签 | 期望 | 不符说明 |
|---|---|---|
| `<li>/<ul>/<ol>` | **0** | 正文混进了 markdown 列表，微信不渲染 → 缩进/编号乱 |
| `<h2>` | = 小标题数 | 小标题漏写 `## ` 前缀 → 没有大字体与彩色下划线 |
| `<strong>` | = 加粗金句数 | 转 HTML 时粗体丢失 |
| `<img>` | = 正文图数 | 少了就是写了 `file://` 前缀没被替换（草稿里图会丢） |
| `thumb_url` | 非空 | 封面没上传成功 |

2026-09-13 实测一篇（约 1950 字）：`0 / 4 / 13 / 1`、封面非空 ✓。

## 4. 日更定时任务（2026-09-13 起已存在，不必重新设计）

- cron job `4b552ab71572`「公众号文章日更-存草稿」：**每天 23:00**，产出 1 篇，**只存草稿箱、不群发**；provider/model pin `cline_local / dots-studio/dots-3-note-preview:free`（pin 后必须复核落盘值）。
- 流程：选题（多源热榜 + 双渠道查重：公众号归档标题 + 微头条台账）→ 核事实（政策类核到发布机关/文号/施行日期/条款号原文）→ 写作（`gzh-viral-writer`，3 标题候选 + `## 01/02/03` 结构）→ 配图 → **DeepSeek 网页版终审** → `run_pipeline` 存草稿 → batchget 验证。
- 公众号版终审：`ds_web_review.py <文稿> --mode gzh --timeout 540 --json`（自动取本号最近 10 篇标题查重）。`verdict=FIX` → 按「必改项」改稿并**重跑**（最多 2 轮），PASS 才存草稿。

### 配套脚本（都在 `wechat-ai-publisher/scripts/`，本机已存在）
- `prep_gzh_images.py` — Pexels 实拍 → 封面 2.35:1（940×400）+ 正文图 16:9（1080×608），自带暗/亮像素自检防过曝废图；**产出后必须逐张看图确认**。
- `verify_gzh_draft.py` — `draft/batchget` 验证 title / 封面 / 正文 `<img>`≥1 / `<li>`=0，**字节级 `.decode('utf-8')`**。
- `delete_draft.py <media_id>` — 改稿后换新版时先删旧稿。

### 坑：`53407 定时发布中，无法删除或修改`
草稿在公众号后台被设成「定时群发」后，API 就删不动也改不动。处置：**绝不要再建一份同题重复稿**，直接告诉用户去后台取消定时/确认发布，再删旧稿。

## 5. 外部终审在哪真有用（实测）

同一篇稿子跑 `--mode gzh` 终审，抓到的基本都是**写稿人自己算错/引错**的：时薪折算数量级写错（“差不到三块钱”实际差 0.3 元）；法规引文漏字（“统一的工作时间”写成“统一工作时间”）；口径不一致（“两个月”vs“52 个工作日”）；同一句式（“不是…是…”）出现 3 次；把具体行业点名成“容易踩底线”（易被读成行业贬损）。

**已知误报（要写进 prompt，避免白改一轮）**：终审会报“正文图是本地路径 `![...](/tmp/xxx.jpg)`，微信无法访问”——这是**误报**，`run_pipeline` 存草稿时会自动上传并替换成微信素材 URL。

## 6. 交付给用户的汇报格式（用户认可的那版）

标题 3 候选（标注公式、说明草稿用的哪个）→ 一句话“打什么情绪、写给谁” → 正文结构逐节一句话 → 合规与质检清单（去 AI 味、事实逐条、HTML 自检数字）→ 归档路径 → 封面/配图说明 → 末尾给 2-3 个可选后续动作（换标题/换封面/接 DeepSeek 终审）。
