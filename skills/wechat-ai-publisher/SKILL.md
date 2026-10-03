---
name: "wechat-article-publisher"
description: "公众号发布流水线：压图、传素材、转HTML、存草稿、归档。含微信不认列表、batchget验证、废图自检等坑。"
---

# 微信公众号文章自动化发布流水线

把素材/选题/链接变成一篇排版好的文章，压缩配图、上传微信素材库、转微信 HTML、存入指定公众号草稿箱并归档。

## 配置（两种方式，任选）

### 方式 A：.env 文件（推荐，避免泄露密钥到命令历史）
在 skill 目录创建 `.env`：
```
WECHAT_APP_ID=<your_app_id>
WECHAT_APP_SECRET=<read_from_config>
MARKDOWN_THEME=orange
```
- `MARKDOWN_THEME` 主题留空=由 Agent 按内容自动选；历史/文学类可选 orange 或 default；新闻/社会类可选 purple 等。

### 方式 B：命令行传参
`--app-id` / `--app-secret` / `--author` 等，逐项传参（不推荐，密钥易入命令历史）。

> ⚠️ **变量名对照**（容易混淆，注意区分）：
- `thumb_media_id`：**封面**在微信素材库的 media_id（每次上传封面会变，须以本次上传返回为准）
- `media_id`：**草稿**的 media_id（创建草稿后返回，用于更新/删除）
- 两者不同，别混用。

## 依赖
```
pip install requests markdown Pillow
```

## 工作流（六步）

### Step 1 收集与整理素材
整理标题、作者、摘要、正文 Markdown、封面图路径。

### Step 2 撰写文章（可插拔）
写作步骤可插拔：**民生/职场/情绪爆款文 → `gzh-viral-writer`**（本机已装：选题模型、八大标题公式、01/02/03 观点文结构、去 AI 味清单）；历史类 → `history-social-writing`；新闻社会类 → `news-social-writing`。

> ⚠️ 旧文档提到的 `wechat-article-writer` / `laoluo-article-writer` **本机不存在**（悬空引用，别照着找）。

> ⚠️ **正文不得重复标题**：`article.md` 第一行**不要**写 `# 标题`。标题字段由 `--title` 单独传入；若正文顶部再放一级标题，转 HTML 后会在**正文最上方重复显示标题**（已踩坑）。

> ⚠️ **正文任何位置都不要用 markdown 列表（已踩坑·硬性）**：不只文末参考文献——包括**正文中间的时间线、要点、步骤列表**（`- `、`1. ` 都会被转成 `<ul>/<ol>/<li>`），而**微信编辑器不渲染 `<li>` 的默认样式，每个 `<li>` 自带 `margin-left` 缩进**，最终用户在微信里看到"莫名其妙缩进、编号乱、有空行"。**正文任何位置的同类内容都必须写成普通段落**：顶格、可用 `**年份**——内容` 或分号/换行分隔的纯文本。发布后务必到微信后台核对排版。

### Step 3 配图处理
封面图 **必须**（公众号草稿强制要求）。

- **正文图片数量要克制（已踩坑·重要）**：别按"每 500 字 1 图"贪多硬塞。**常见正文只需 1 张图**（居中插入一处即可，多数用户偏好一张），插入数量**先跟用户对齐**；只有明确要图文并茂的题材才多放。宁缺毋滥，正文主体仍是文字排版。
- 压缩：PIL，封面建议 ≤800KB（微信上限 2MB），配图 ≤600KB。
- 上传到微信素材库，拿到 `thumb_media_id` + `url`。
- 记录 `thumb_media_id`（封面）和正文中每张图的 `url`（**微信草稿要求正文图必须用微信素材库的 url，不能直接外链**）。

> ⚠️ **正文图片引用格式（已踩坑·硬性）**：在 `article.md` 里写正文图必须用**无前缀的路径**——`![说明](/tmp/xxx.jpg)`，**绝不要写 `file:///tmp/xxx.jpg`**。因为 `run_pipeline.py` 的 `_replace_local_images` 只按 `](路径)` 或 `](文件名)` 精确匹配替换，`](file://...)` **匹配不上**，图引用会原样进 HTML，最终**正文图在微信草稿里丢失**（草稿箱验证正文 `<img>` 数量=0）。
> 写完 markdown 后务必自查：`grep -n 'file://' article.md` 应为空。

> ⚠️ **网络抓图必须验证内容（已踩坑·硬性）**：从互联网/新闻页抓来的图，**绝不能凭网页文字描述推断画面内容**就直接用。坑：曾把一篇报道里郑国霖"拉黄包车"的配图，凭文字假设成该场景，实际抓到的却是**另一张古装剧剧照**（两个男演员对视），发到草稿箱被用户识破。**抓图后必须用千问视觉模型（qwen-vl）识图确认**：画面主体是谁/在做什么/什么场景/有没有文字水印，确认与用途相符、无文字，才可当封面/正文图。有文字水印（如"头条@xxx""XX时报"）的须先裁掉或换图，裁切前让视觉模型给出**主体坐标与安全裁剪范围**，避免裁到人物。新闻图常带顶部白边/底部字幕，注意甄别。

> ⚠️ **封面废图自检（已踩坑·重要）**：AI 生图偶发产出 **99% 全黑/全暗的废图**（看似有效 JPEG、尺寸正常，但内容全黑，用户看到的是"几个横杠"）。**发布前必须验证图片非废图**：
> ```python
> from PIL import Image
> im = Image.open('cover.jpg').convert('L')
> hist = im.histogram(); total = im.width*im.height
> dark = sum(hist[:85])/total*100
> # dark > 90% 即为过暗废图，须重新生成
> ```
> ⚠️ **注意：`dark>90%` 只判"过暗"废图，不能反过来判"全亮"**。今天踩坑：qwen-image 生成的封面 99.5% 全亮（`bright=sum(hist[170:])/total` 近 100%），但视觉上却是**正常的明亮图**（淡蓝紫渐变星空背景+发光球体）。**遇到全亮不要急着当废图重生成，先用千问视觉模型（qwen-vl-max）看图确认内容是否正常**。废图且需重新生成时，qwen-image 偶发连出黑图，可改更明亮的 prompt（如"明亮浅色渐变背景+高光主体"）提高成功率。

> ⚠️ **封面默认纯图不带字（已踩坑·重要）**：**封面图片本身默认不带任何叠加文字**——标题、副标题等文字交给公众号封面库/标题字段（`--title`）呈现。**不要自作主张在封面图上叠标题文字**（用户往往不要）。若确实需要叠字，须先跟用户确认；不确认则用纯图。
> 用 AI（如千问图像）生成的图做封面时：
> 1. **先生成无文字图**：prompt 里明确写"画面中不要出现任何文字/汉字/题字/印章/签名/水印"。
> 2. **先让视觉模型看图验证**（人物是否完整、有无被裁/遮挡、是否确实无字）。
> 3. 若图片源自 AI 且图内已有竖排题字/印章（如"诸葛孔明"+朱红印），**用户明确不要时须重新生成无字版**，不能直接裁掉（裁切可能裁到人或留字）。
> 4. **明暗对比**：若最终需叠字，深色图用浅字、浅色图用深字；避开图内文字与人脸主体。
> 5. **裁剪留天头**：比例不符公众号头图（2.35:1，如 900×383）时裁切，保住主体（人物头顶留天头，防二次裁切到冠顶/头顶）。

### Step 4 Markdown → 微信 HTML
```
$PYTHON $SCRIPTS/markdown_to_wechat_doocs.py \
  --input 正文.md --output 输出.html --theme <主题>
```
支持主题：`default/green/purple/orange/cyan`（注意：**无 brown**，历史版若记 theme=brown 需映射到这些之一）。

> ⚠️ **小标题必须写 `##`（已踩坑）**：正文小标题若只写 `01 xxx` 不带 `## 前缀`，本脚本会把它当普通段落，**失去大字体和彩色下划线**。务必 `## 01 xxx`。小标题内容要极简（序号+几个字）。

### Step 5 创建草稿
```
$PYTHON $SCRIPTS/create_draft.py \
  --title "标题" --content "$(cat 输出.html)" \
  --thumb_media_id "封面thumb_media_id" \
  --author "棱镜折射" --digest "摘要"
```
成功返回 `{"media_id":"..."}`。

### Step 6 归档
正文归档到 `articles/published/`，封面到 `articles/covers/`，微头条到 `articles/toutiao/`，并写 `_meta.json`（title/media_id/thumb_media_id/theme/cover/created_at）。

### 一键串联（run_pipeline，推荐）
`run_pipeline.py`：压缩封面→上传封面→上传正文图并替换→转HTML→建草稿→归档。

## 日更定时任务（2026-09-13 起）

- cron job `4b552ab71572`「公众号文章日更-存草稿」：**每天 23:00**，产出 1 篇文章，**只存草稿箱、不群发**；模型 pin `cline_local / google/gemma-4-26b-a4b-it:free`（免费，与微头条任务一致）。
- 完整流程：选题(多源热搜+双渠道查重) → 核事实(≥2 信源，政策类核到文号/条款原文) → 写作(`gzh-viral-writer`，3 标题候选+01/02/03 结构+去 AI 味) → 配图(`scripts/prep_gzh_images.py` + vision 验证非废图) → **DeepSeek 网页版终审** → `run_pipeline` 存草稿 → `scripts/verify_gzh_draft.py` 验证。
- **DeepSeek 终审（硬性）**：`python3 ~/.hermes/skills/toutiao-micro-publish/scripts/ds_web_review.py <文稿.md> --mode gzh --timeout 540 --json`
  - `verdict=FIX` → 按回答里的「必改项」逐条改稿并**重跑**（最多 2 轮）；`PASS` 才允许存草稿
  - 报错含「未登录/sign_in」→ 停止并发邮件；其它报错重试 1 次，仍失败不阻断但要在回执里注明「DeepSeek 终审未执行」
  - 依赖：无头 Chrome(9222) 已登录 chat.deepseek.com（登录会过期，过期需重新扫码）；脚本自动取本号最近 10 篇标题做查重

### 新增脚本
- `scripts/prune_drafts.py`：**草稿箱清理**（2026-10-03 起）。删 N 天前的**图集**草稿并把对应话题从 `topics.json` + 脚本内置表同步摘掉；默认 `--days 2`、默认**不动非图集草稿**（手写/日更文章），加 `--include-articles` 才会连文章一起删。另有 `--dry-run`。
  - cron job `e11f232f4c79`「草稿箱清理-每天09:00（图集）」→ 包一层 `~/.hermes/scripts/prune_gzh_drafts.sh`，`no_agent=true`，stdout 即投递内容。
  - `sync_pool()` 会同时给 `topics.json` 和 `pexels_gallery_draft.py` 各留一份 `.bak-<时间戳>` —— 只还原一个会造成两源不一致（踩过）。
- `scripts/prep_gzh_images.py`：Pexels 抓图 → 封面 2.35:1(940×400) + 正文图 16:9(1080×608)，带暗/亮像素自检（防过曝废图）。
- `scripts/verify_gzh_draft.py`：用 `draft/batchget` 验证草稿（title / 封面非空 / 正文 `<img>`≥1 / `<li>`=0），**必须 `r.content.decode("utf-8")`**（直接 `r.json()`/`r.text` 会中文乱码）。
- `scripts/delete_draft.py <media_id>`：删草稿（改稿后换新版时用）。**坑：报 `53407 定时发布中，无法删除或修改`** = 该草稿已在公众号后台被设为定时群发，API 动不了；此时不要建重复稿，让用户去后台取消定时后再说。

## 能力边界与限制
- **图片大小**：微信素材图片上限 **2MB**（超了报 `40006`/`45001`）。封面建议压缩 ≤800KB；正文图也需 ≤2MB。
- **文章长度**：微信草稿正文无硬性字数上限，建议单篇 ≤5 万字。
- **草稿更新**：`create_draft.py` 不支持更新已有草稿；改内容用新标题重建草稿 → `draft/delete` 删旧草稿（`freepublish/delete` 可能报 48001 未授权，回退旧接口）。

## 重试与故障排查
| 错误 | 含义 | 处理 |
|---|---|---|
| 40006 / 45001 | 图片超过 2MB | 压缩封面（≤800KB）/正文图（≤2MB） |
| 40007 | thumb_media_id 无效 | 确认封面上传成功返回的 media_id |
| 40125 | invalid appsecret（获取 access_token 失败） | AppSecret 已失效——公众号后台「设置与开发→基本配置→开发者密码」被**重置**过（旧值立即作废），或 .env 里的值被写坏。让用户在后台重置一次 AppSecret，拿到新值后更新 .env。**注意**：此错会表现为"全部图片素材上传失败"（每张图都要先换 token），别误判成图片/网络问题 |
| 48001 | 接口未授权 | 回退用旧接口（如 `draft/delete` 而非 `freepublish/delete`） |
| no_cover | 未传封面 | 公众号草稿强制要求封面，先上传封面拿 media_id |

> ⚠️ **排错别只看 cron 摘要（已踩坑）**：`no_agent` 脚本若用 `tail -5` 汇报，会把 40125 之类的真实原因丢掉，只剩"全部图片素材上传失败"，白查半天。**脚本必须把完整 stdout+stderr 落盘**（如 `~/.hermes/logs/cron/gallery_<ts>.log`），stdout 只留一行摘要，并对 `40125 / invalid appsecret` 单独分流提示。

> ⚠️ **凭证可能中途失效**：同一 AppSecret 可以在几分钟内从可用变为 40125（后台被重置）。判定"是不是凭证问题"最快的办法：直接 `GET /cgi-bin/token` 看 errcode，别先怀疑图或网络。

## 铁律
- 封面图 **必须有**，否则微信拒收草稿。
- **封面默认纯图不带字**（文字交给封面库/标题字段；要叠字先确认）。
- **正文图片宁缺毋滥**：常见 1 张即可，插入数量先跟用户对齐。
- **正文图引用必须无前缀路径 `](/tmp/xxx.jpg)`，禁止 `file:///`**（否则 run_pipeline 替换不上，正文图丢失）。
- **AI 生成的封面/正文图发布前须验证非废图**（dark>90% 为过暗废图重新生成；全亮需 qwen-vl-max 看图确认而非直接重生成）。
- **正文任何位置不用 markdown 列表**（时间线/要点/参考文献都改顶格段落，见 Step 2）。
- 正文图片必须用微信素材库 `url`，外链图片在 App 端不显示。
- 缩略图 ≤ 2MB，建议 JPEG。
- AppSecret 不进日志/文章/prompt。
- 默认只存草稿，群发需人工确认。

> ✅ **发布后务必从微信草稿箱验证，且要用正确的解码姿势（已踩坑）**：仅看本地归档或脚本 stdout 不够，用 `draft/batchget` 拉草稿，检查每篇 `news_item` 的正文 `<img>` 数量=期望值、封面 `thumb_url` 非空。
> ⚠️ **batchget 验证中文标题时，`requests` 的 `r.json()` 会把微信返回的 UTF-8 字节误当 Latin-1 解码，导致终端显示成 `ä»\x96...` 假乱码**——这是显示层问题，不是存储问题。**正确姿势：看 `r.content` 原始字节，用 `.decode('utf-8')` 验证**，例如 `raw[r.find(b'title'):raw.find(b'title')+200].decode('utf-8')`，或对 `r.json()` 的字符串字段做 `s.encode('latin-1', errors='ignore').decode('utf-8', errors='ignore')` 还原。别用 `ensure_ascii=False` 去"证伪"（它只能证明显示问题，证不了字节好坏）。公众号后台存储实际是正确的。

## 千问（DashScope）生图/看图排雷（已踩坑）
- **看图（视觉分析）**：用 `qwen-vl-max`（识图更稳），走**原生接口** `https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation`，body 用 `{"model":"qwen-vl-max","input":{"messages":[{"role":"user","content":[{"image":"data:image/jpeg;base64,..."},{"text":"提问"}]}]}}`，返回在 `output.choices[0].message.content`（可能为 list，需拼 text）。可用于：图是否有文字/水印、画面主体坐标（供裁水印）、内容场景确认。**Key 从 `openclaw.json` 的 `models.providers.dashscope.apiKey` 读**（勿硬编码）。
- **生图（qwen-image-3.0）**：走**原生接口** `https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation`，body 用 `{"model":"qwen-image-3.0","input":{"messages":[{"role":"user","content":[{"text":"prompt"}]}]},"parameters":{"size":"1280*720"}}`。**返回是同步的**：图在 `output.choices[0].message.content[0].image`（URL），不是 `task_id` 异步轮询格式。
- ⚠️ **别用错路径**：`text2image/image-synthesis`、`image2image/image-synthesis`、`images/generations`（OpenAI 兼容）对 qwen-image 都会报 400 "url error" 或 404。
- ⚠️ **生图限流**：同一账号短时间多次请求会 429 `Throttling.RateQuota`。探测接口别连发，正式生成尽量一次到位，限流后冷却 1-2 分钟再试。**Key 从配置文件读取**（勿硬编码带省略号/被脱敏破坏的字符串，否则 401 InvalidApiKey；建议写临时 key 文件或读配置）。
- **无需文字图**：若成品要"纯图不带字"，prompt 必写"无任何文字/题字/印章/签名/水印"，并生成后让视觉模型确认。
- 生成后可让视觉模型看图验证结果（是否风格正确、要素齐全、无字、适合做封面）。
- **rule：任何封面/正文图（AI 生成或网络抓取）在进草稿前都必须先过视觉模型验证**；网络图尤其要确认"是不是我以为的那张"，不要凭文字推断。

## 资源
- 脚本文档见 `scripts/`。
- 写作参考：`history-social-writing`、`news-social-writing`。

---

# 图集草稿流水线（pexels_gallery_draft.py）

## 概述

每小时/每 30 分钟产出一期公众号图集草稿：Pexels 抓图 → 翻转+滤镜 → 两版产出 → 传封面+正文图 → 建**图文消息(news)**草稿（正文末尾带可点击的小程序文字链）→ 同步小程序云存储。

> ⚠️ **类型必须是 news，不能是 newspic（2026-10-01 踩坑·硬性）**：见下方「小程序文字链」一节。用 `newspic` 时正文里写 `#小程序://...` 发布后是**死文字点不动**，别再用。

## 话题池

- 活跃池在 `scripts/topics.json`（脚本优先读它），`_BUILTIN_TOPICS` 是兜底，两者内容保持一致。
- **2026-10-02 品质筛选（用户要求）**：246 → **181 条**。用户口径：*排除破败 / 缺乏美感的场景，只留大众熟知、宏大、漂亮、大气、有美感的*。摘掉 65 条，分四类：
  1. **破败陈旧**：老理发店、缝纫老店、修鞋摊、修表匠、老照相馆、旧书摊、旧邮局窗、老钟楼、骑楼老街、红砖厂房、圆明园（废墟）、奥林匹亚遗址、喀什老城、吊脚楼。
  2. **小景 / 建筑细部**（不宏大）：铁艺阳台、旋转楼梯、拱廊、石板小巷、阶梯住宅、山城阶梯、老城门、滩涂倒影、湿地芦苇、芦苇荡夕阳、海边礁石、红树林、秋日葡萄园。
  3. **冷门地区性**：碉楼、红砖厝、糖画手艺人、竹编工匠、染布坊、皮影戏、木偶戏、赶海、采茶人、渔港归来、楠溪江、潮州牌坊街、田子坊、武康路、南锣鼓巷、重庆轻轨。
  4. **拥挤杂乱**：台湾/曼谷/海鲜夜市、夜市烧烤摊、糖葫芦摊、庙会、夜宵摊、夜市游戏摊、早市摊位、面包店、面馆烟火。
  人文生活类基本清空，只留 花店门口 / 早茶点心 / 龙舟训练。备份：`topics.json.bak-<时间戳>`。
- **2026-10-02 扩充国内池**：+108 条国内景点/建筑（筛选前累计 246）。覆盖北京(颐和园/什刹海/鸟巢/央视大楼/香山红叶/慕田峪/雍和宫)、上海(豫园/外白渡桥/上海中心)、江浙水乡(苏州园林/拙政园/周庄/乌镇/西塘/夫子庙/瘦西湖/灵隐寺/千岛湖)、皖赣闽粤(皖南古村落/三清山/庐山/景德镇/龙虎山/鼓浪屿/武夷山/霞浦滩涂/丹霞山)、湘鄂(岳麓山/洞庭湖/三峡/黄鹤楼/恩施大峡谷)、川渝(都江堰/青城山/乐山大佛/四姑娘山/海螺沟/洪崖洞/长江索道)、云贵(元阳梯田/玉龙雪山/大理古城/黄果树/千户苗寨/荔波/万峰林)、西北(张掖丹霞/嘉峪关/月牙泉/茶卡盐湖/天山天池/帕米尔/赛里木湖/塔克拉玛干/贺兰山/沙坡头/秦岭)、东北(长白山/松花江雾凇/哈尔滨冰雪大世界/圣索菲亚教堂/漠河/大连星海)、青藏内蒙(纳木错/珠峰大本营/羊卓雍措/冈仁波齐/阿尔山/巴丹吉林)、港澳台(澳门大三巴/九份/阿里山/垦丁/太鲁阁)、国内建筑(国家大剧院/苏州博物馆/哈尔滨大剧院/天津之眼/蒙古包/侗族鼓楼/藏族寺庙/苗寨/徽州牌坊)。
- ⚠️ **涉军/阅兵题材做不了（2026-10-02 实测）**：Pexels 按国家搜阅兵会大量张冠李戴——`chinese honor guard` 返土耳其兵、`us army parade` 返墨西哥兵、`north korea parade` 返阿根廷兵+韩国警察、`italian military parade` 返西班牙骑兵、`russian victory day` 主要是苏联勋章特写。**搜索词能命中 ≠ 图对**，必须按 `photos[].alt` 过滤国家关键词再逐张看图。可靠的只有法国(巴士底日)/印度(共和国日)/英国(皇家卫队)/土耳其(Anıtkabir)。
- `load_topics()` 兼容 `[{"cn","en"}]` 和 `[["cn","en"]]` 两种格式（旧版只认 dict，遇到数组抛 AttributeError 就静默回退内置表——现存的 topics.json 曾是这个格式）。
- 换池前用 Pexels API 抽查英文词（`per_page=8~15`，`<8` 条算偏瘦要换词）：免费额度 200 次/小时，别在别处把额度用光。注意 `per_page=15` 全返 15 只说明"≥15"，不代表真的多。
- 已删除的类：交通工具、宇宙天文、人物肖像、艺术展览、动物、美食。
- 保留：自然景观、建筑、世界地标/古迹、人文生活、夜市。

## 图片处理

1. Pexels 搜索 → 只收横图（width > height）→ 下载原图
2. md5 去重：查 `logs/gallery_sent_md5.json`，发过的跳过
3. `process_image()`：左右翻转 + 对比度/色彩/亮度微调 + 轻噪点，短边 >2500 先缩到 2500
4. 产出两版：
   - **压缩版**（`final_*.jpg`，≤600KB）→ 传微信**永久素材**，取 `media_id` 当**封面**（`thumb_media_id`）
   - **全尺寸版**（`full_*.jpg`，不压缩）→ 落盘；再压到 ≤900KB 走 `uploadimg` 拿 URL，进**正文 HTML**（2026-10-01 起）

## 小程序文字链（2026-10-01 起）

正文末尾固定一行，整行可点击跳小程序：

```
高清原图看这里👉 这组图真的每一张都能当壁纸！
```

### 为什么之前点不动（根因）

| 文章类型 | content 字段能力 | 小程序链接 |
|---|---|---|
| `newspic`（图片消息/小绿书） | **只支持纯文本**（+商品标签） | 写 `#小程序://` 是死文字，**发布后点不动** |
| `news`（图文消息） | **支持 HTML** | 用 `<a data-miniprogram-appid=...>` 才可点击 |

官方文档原话（draft/add）：*"图片消息则仅支持纯文本和部分特殊功能标签如商品"*。
所以 `newspic` 里塞 `#小程序://棱镜图库/xxx`、`weixin://`、`<a href>` 全都白费——HTML 在 newspic 下直接报 `45166 invalid content`。

### 正确写法（`news` 的 content）

```html
<p><img src="<uploadimg 返回的 mmbiz URL>" style="width:100%;"/></p>
...
<p><a data-miniprogram-appid="wx489060715b335aaf"
      data-miniprogram-path="pages/index/index"
      data-miniprogram-nickname="棱镜图库"
      data-miniprogram-type="text" href="">高清原图看这里👉 这组图真的每一张都能当壁纸！</a></p>
```

- `data-miniprogram-path` 不带开头的斜杠（后台界面显示 `/pages/index/index`，API 写 `pages/index/index`）。
- 正文 `<img>` 的 URL **必须**来自 `POST /cgi-bin/media/uploadimg`；素材库永久素材的 URL 会被过滤。
- 封面用 `POST /cgi-bin/material/add_material?type=image` 的 `media_id`（≤2MB）。
- **图与图之间、以及最后链接之前各留一个空行**：用 `<p><br/></p>` 当分隔符拼接（`"<p><br/></p>".join(blocks)`）。直接 `"".join()` 连排会挤成一片。微信存库时会规范成 `<br  />`，回读校验别按 `<br/>` 原文匹配。

### 其他坑

- **`draft/update` 不能改文章类型**：`newspic` → `news` 会报 `53403 不支持修改文章类型`。要换类型只能**新建草稿 + 删旧的**（`draft/delete`）。
- **`draft/batchget` 才是列草稿的接口**；写成 `draft/getdraft` 会报 `40066 invalid url`（误导性报错）。单篇用 `draft/get`。
- **回读校验**：建完草稿后 `draft/get` 检查 content 里 `data-miniprogram-appid` 是否还在（被过滤就会丢）。
- **发布后草稿会从草稿箱消失**，所以在草稿箱里找不到≠没建过。

## 标签映射（2026-09-25 新增）

`cloud_stash()` 写入云数据库时自动按 `topic` 从 `TOPIC_TAG_MAP` 匹配标签，一对多。标签类别：风景、建筑、旅行、植物、星空、运动、美食、科技、人像。映射表在 `pexels_gallery_draft.py` 的 `TOPIC_TAG_MAP` 段，未在表中的话题回退为 `[topic]`。

## 小程序云存储同步（2026-09-25 新增）

草稿创建成功后自动转存到微信小程序云环境 `cloud1-d9gkyv32i776bf4cc`：

| 版本 | 云存储路径 | 数据库字段 |
|------|-----------|-----------|
| 全尺寸原图 | `images/original/<ts>-<rand>.jpg` | `originalFileID` |
| 压缩缩略图 | `images/thumbnails/<ts>-<rand>.jpg` | `thumbnailFileID` |

写入 `images` 集合，字段：`_id` / `_openid` / `title` / `category` / `categories` / `tags` / `originalFileID` / `thumbnailFileID` / `width` / `height` / `uploadTime` / `downloads` / `status` / `reviewer` / `reviewTime`。

云转存失败不影响主流程（只打日志不抛异常）。

## 关键 API 踩坑

- **tcb 云数据库接口**：body 只有 `env` + `query`（JS 表达式字符串），没有 `collection` 字段。多传 collection 会 47001。
- **tcb uploadfile**：返回 `token` / `authorization` / `cos_file_id` / `file_id`，不是 `cos` / `fileID`。
- **COS 上传**：multipart/form-data，字段 `key` / `Signature` / `x-cos-security-token` / `x-cos-meta-fileid` / `file`。
- **access_token**：云数据库接口偶尔 40001 "invalid credential"，用 `cgi-bin/stable_token`（POST）替代 `cgi-bin/token`（GET）更稳。
- **databasequery**：query 格式 `db.collection('images').limit(3).get()`，返回 `data` 是 NDJSON 字符串数组。
- **NameError `full_files`**：删 `MEDIA:` 输出时容易把 `full_files = sorted(glob.glob(...))` 一起删掉，导致 JSON 汇总里引用未定义变量。删输出循环时务必保留变量定义行。
