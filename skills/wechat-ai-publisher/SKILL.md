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
pip install requests markdown Pillow numpy
```
> ⚠️ `numpy` 是图集画质闸门（`qc_sharpness()`）的硬依赖，漏装会在 QC 阶段报 `ModuleNotFoundError`。cron 包装脚本要显式挑一个能 `import numpy, PIL, requests` 的解释器（PATH 会随网关重启漂移），见 `hermes-cron-pipeline-ops` 的 `references/pexels-gallery-ops.md` §10。

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

## 正文排版强调（用户定稿）

- **文章标题是纯文本字段，不能上色**：微信 `title` 不接受任何 HTML/CSS。用户说“标题加颜色”时，只能给**正文小标题**上色，并直接告诉他文章标题改不了颜色，别硬做。
- **小标题格式**：`## <span style="color:#1E4E8C">01 xxx</span>`。序号 `01`–`06` 必须带（用户明确要求编号）；颜色跟主题边线同色系——`default` 边线 `#3f51b5` 配深蓝 `#1E4E8C`，换成 `orange` 就必须换文字色，别红字配橙线。
- **重点/反常识句用红色虚线**：`<span style="border-bottom:1px dashed #C0392B;padding-bottom:2px;">…</span>`。**不要用 `text-decoration-style:dashed`**——微信编辑器对那条 CSS 支持不稳，`border-bottom` 才是可靠写法。
- 下划线只圈 15–30 字的短句（数字对比、反常识结论、核心洞察）；整段下划线会糊成一片，用户要的是“点一下”，不是“划一片”。
- raw HTML（`<span>` / `<u>` / `<p><a data-miniprogram…>`）经 `markdown_to_html_doocs` 会原样保留，可放心用；改完用 `draft/get` 数 `<h2>` 与虚线 span 的数量核对。
- 改标题、加编号、加样式都属于**内容变更**：重新跑 `run_pipeline` 建新草稿 → 删旧草稿（旧 `media_id`）。不删就会出现两篇同名稿，用户会以为改失败。

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

- cron job `4b552ab71572`「公众号文章日更-存草稿」：原为每天 23:00，**2026-10-03 用户要求停掉，已 ⏸ 暂停**。恢复时注意：清理 job `e11f232f4c79` 每天 09:00 会删掉 2 天前的**所有**草稿（含文章），文章日更若恢复需自行权衡保留期。
- 完整流程：选题(多源热搜+双渠道查重) → 核事实(≥2 信源，政策类核到文号/条款原文) → 写作(`gzh-viral-writer`，3 标题候选+01/02/03 结构+去 AI 味) → 配图(`scripts/prep_gzh_images.py` + vision 验证非废图) → **DeepSeek 网页版终审** → `run_pipeline` 存草稿 → `scripts/verify_gzh_draft.py` 验证。
- **DeepSeek 终审（硬性）**：`python3 ~/.hermes/skills/toutiao-micro-publish/scripts/ds_web_review.py <文稿.md> --mode gzh --timeout 540 --json`
  - `verdict=FIX` → 按回答里的「必改项」逐条改稿并**重跑**（最多 2 轮）；`PASS` 才允许存草稿
  - 报错含「未登录/sign_in」→ 停止并发邮件；其它报错重试 1 次，仍失败不阻断但要在回执里注明「DeepSeek 终审未执行」
  - 依赖：无头 Chrome(9222) 已登录 chat.deepseek.com（登录会过期，过期需重新扫码）；脚本自动取本号最近 10 篇标题做查重

### 图集脚本双模式（2026-10-03 改造）
`pexels_gallery_draft.py` 现在**一个脚本、两种产出**，由 `--mode` 控制：
- `news`（默认）= 图文消息，正文 9 图 + 末尾可点击小程序文字链
- `newspic` = 纯贴图，**无正文、无链接**（content 只支持纯文本，写链接也点不动）

两种模式共用同一批图（搜索→下载→画质闸门→翻转滤镜→压缩），区别只在建稿那一步：
- `news`：正文图走 `uploadimg` 取 URL 拼 HTML；`create_news_draft()`
- `newspic`：图走**永久素材**取 `media_id`（`newspic` 要 `image_media_id`，不能用 uploadimg 的 URL）；`create_newspic_draft()`

**横版**：`ori` 已硬编码为 `landscape`（用户要求图集一律横版），不再随机选方向。

### 需求识别：“图集”不等于“文章”（硬性）

- 用户说“做个图集 / 九张美景图 / 不要文字 / 带小程序链接” → **直接跑 `pexels_gallery_draft.py --mode news`**，不要先写文章。两者产物完全不同：文章走 `run_pipeline`（一篇图文，正文是字），图集是一组纯图片 + 链接。做错方向等于白做，用户会直接炸。
- 只有用户明确说“文章 / 推文 / 写一篇 / 要正文”时才写文章。拿不准时**先问一句**要文章还是图片组，别自作主张写一篇。
- **产出张数必须等于用户要求**（默认 9）。脚本 `MIN_VALID_IMAGES=5`，有效新图只有 7 张也会报 `status: success`；所以验收不能只看 success，要用 `draft/get` 数 `content.count('<img')`，不足就按上一节“有效新图不足”的补救流程重做。
- 盯任务进程用 `pgrep -f "pexels_gallery_draft.py --mode news "`（末尾加空格）或 `pgrep -af ... | grep -v newspic`。`news` 是 `newspic` 的前缀，不加边界会把每小时的贴图任务误判成图集任务还在跑。

### 图集封面：多图竖拼（用户指定，纯图不带字）

用户要的形态：**一张封面里竖着并排几条当期图集的图，不叠加任何文字**（标题只走草稿 `title` 字段）。早期那版“顶部黑标题 + 图上地名”已被否掉，**不要再往封面里加字**。

六条等宽直接硬拼是最容易翻车的做法：六张不同照片的地平线各不相同、太阳会出现好几个、色温一跳就像“百叶窗”。用户对这种图的评价是“色彩过渡不好看”。

**最终定稿（用户两次拍板）：最初那版——六条等宽、纯图无文字、按给定顺序拼，不排序、不调色、不羽化。**

用户先说想按色调排序，看到排序版后又明确回「我要的是最初那一版」——**排序也被否了**。所以不要再自作主张加排序、筛选或调色。

1. `cover_card6.py --no-text`，六条等宽满铺，纯图无文字，1080×648；需要时再出 1080×460（公众号 2.35:1）。
2. 图片顺序 = 传入顺序（通常取当期图集前 6 张），不重排。
3. 唯一允许的干预：某张明显是冷色、雾天或糊图时**换掉那张图**——不是给它调色，也不是重排顺序。
4. 不加标题、地名、水印；不做色彩迁移、整体叠色、接缝羽化、暗角。用户要的就是原图硬拼。

**别再拿“色彩过渡”去说服自己加工**：不同照片的曝光、云量、地平线本来就不同，排序只解决冷暖相撞，解决不了明暗跳变；加滤镜会被判“失真”。能改的只有换图。

已试过但用户**明确不要**的版式（别再提议）：一大 + 2×2 网格（`--layout grid`）、一大 + 三条（`--layout main3`）、三条等宽（`--layout three`）、Reinhard 色彩迁移版（`cover_card6_v4.py`）。这些脚本保留备用，但默认不动。

**不要给封面加调色/羽化（用户明确否决）**：Reinhard 色彩迁移、整体暖色叠层、暗角、接缝羽化这一整套都试过，用户的评价是“失真”，最后还是回到原图硬拼。`cover_card6_v2/v3/v4.py` 只作实验留档，默认不要用。

**唯一例外**：某张图明显是冷色或雾天、会破坏整张时，正确做法是**换掉那张图**，不是给它调色——`cover_card6_v4.pick()` 里的暖色/饱和度/亮度筛选可以单独借用。

尺寸：默认 1080×648（参考图比例）；公众号列表按 2.35:1 裁切，需要时再出一版 `--size 1080x460`。

> ⚠️ 封面是审美项：出图前先用 `vision_analyze` 自检“地平线是否统一 / 有没有多个太阳 / 有没有跳色”。**版式已定稿，不要再发版式样张让用户挑**（他会直接回“我要最初那版”）；只在选图有争议时给 2–3 张候选。详细参数见 `references/cover-design.md`。

### 调度拆分（频率/启停以 `cronjob list` 为准）
- cron `9d58e7843134`「公众号图集-每2小时（炫酷风景·图文消息）」→ `0 */2 * * *`，跑 `gallery_draft_daily.sh`（`--mode news --count 12`）。当前启用，用户要求图集每次 **12 张**。
- cron `6b86d039a651`「公众号贴图-每4小时（纯贴图，无正文）」→ `0 */4 * * *`，跑 `gallery_draft_hourly.sh`（`--mode newspic`）。当前启用，用户把原来的每小时改成了每 4 小时。
- 改频率只动 cron 的 schedule（`cronjob_manage update`），改张数只动包装脚本的 `--count`；不要改脚本里的默认值（9），否则手动跑和定时跑会分叉。
- 两个任务并存时一天约 36 条草稿，会把草稿箱刷屏；要"停一个"时先分清：**带小程序链接的是 news（图集），无正文的是 newspic（贴图）**，按用户指的那一种停，别两个一起停。
- 实测（金丝猴，贴图模式）：`article_type=newspic`、正文 0 图、无文字、无小程序标签、封面有、云转存 9 ✅
- ⚠️ **贴图模式的"前两张重复"坑（2026-10-03 踩过）**：`newspic` 的 `image_list` 本身就是全部贴图，**不需要单独的封面**（`thumb_media_id` 是 `news` 模式才用的）。之前把 `processed[0]` 的压缩版当第 1 张、又把 `full_size[0]` 的压缩版当第 2 张——**同一张原图的两个压缩版本**，视觉上完全一样，用户一眼看穿。正确做法：贴图模式直接从 `full_size` 传 9 张，`image_media_ids` 从空列表开始 append。另加保护：贴图有效图不足 3 张直接抛异常，不静默出 1 张图的草稿。

### 磁盘空间与产物清理（2026-10-15 踩坑·硬性）

图集每次跑都会在 `/tmp` 落一个 `gallery_out_<时间戳>/` 目录（原图 + 处理图 + 缩略图，单次 10+MB）。**历史产物从不清理，会把磁盘慢慢塞满**——本机 `/dev/vda2` 只有 50G，2026-10-15 实测被 717 个 `gallery_out_*` 吃掉 31GB+，磁盘 100%，图集直接 `No space left on device` 失败。

**已修**：脚本加了 `_purge_old_galleries()`，**每次跑图集前自动删 3 天前的 `gallery_out_*` 目录**（保留最近 3 天产物用于排错）。清理动作会打一行 `🧹 清理历史产物：删掉 N 个 3 天前的 gallery_out_* 目录`。

**排障铁律**：图集 job 报 `No space left on device` / 下载失败 / 产出不足 → **第一反应查 `df -h /`**，别先怀疑 Pexels API 或网络。磁盘满是这个流水线最常见的假故障。

**长期方案（待用户拍板）**：`/tmp` 是 tmpfs 还是磁盘分区影响清理策略——如果是 tmpfs 则不存在磁盘问题（只是内存占用）；如果是磁盘分区则必须设保留窗口。当前用 3 天窗口，如需更激进可改成 1 天。

### 出图画质闸门（2026-10-03 新增）
用户要求「构景优美，不要模糊／灰暗陈旧的图」，故在**下载候选后、落盘前**加了一道闸门（`image_quality_ok()`）：
- **锐度**：原图 3×3 分块，取最锐一块的拉普拉斯方差（`qc_sharpness()`）。**不要缩到固定宽度算**——缩放下模糊线索会被抹掉，实测漏检一半以上。
- 阈值 `QC_SHARP_MIN=150`，按真实产物标定：真图最低 65、人造模糊最高 140 → 150 可全拦模糊、误杀约 10%（误杀只是多换一张，代价可接受）。
- **灰暗**：800px 下 `sat<50` 且 `contrast<45` → 剔除。
- **雾景/夜景豁免**：`QC_HAZY_TOPICS`（松林晨雾、云瀑、温泉雾气、峡谷晨曦、雪原日出、银河星空、极光湖面、萤火虫森林、蓝冰洞、瀑布彩虹）阈值降到 60，否则会被误杀。
- 候选数从 `count*4` 提到 `count*6`，被拦后自动换下一张；`--no-qc` 可关闭（排错用）。JSON 输出多一个 `rejected_qc` 字段。
- 实测（火烈鸟群）：候选取 15 张，拦下 6 张（4 张 sharp 20/50/67/120 模糊 + 2 张 sat 22/26 灰暗），留 9 张，vision 复核 6.5～7/10 合格。
- ⚠️ **QC 依赖 numpy，cron 里要钉解释器**：裸 `python3` 可能解析到 Hermes venv（有 PIL/requests、缺 numpy），表现为图片已下载、到 `qc_sharpness()` 才抛 `ModuleNotFoundError: No module named 'numpy'`。包装脚本按能力选解释器，修完先 `--dry-run --count 3` 验 QC 通路。
- ⚠️ **超大拼接图会触发 PIL 解压炸弹（`DecompressionBombError`）**：Pexels 偶发 16000×13000（约 2 亿像素）的图，超过 PIL 默认 1.79 亿像素上限，`qc_sharpness()` 的 `Image.open()` 直接抛异常，**整轮 news 和 newspic 都在 QC 阶段崩掉**（磁盘、网络、凭证都正常，别往那三个方向查）。修法：`Image.MAX_IMAGE_PIXELS = None` 关掉硬上限，打开后先读 `im.size`，`w*h > 60_000_000`（6000 万像素，约 9000×6600）就打印“图片过大”并按不合格跳过；`process_image()` 加同一道保护并 raise ValueError。改完不要等 cron 验证：`Image.new("L", (9000, 9000))` 存一张 JPEG，断言 `qc_sharpness()` 返回 0.0、`process_image()` 抛 ValueError。

### 多路查询去重与强制标题（2026-11-18）

- **多路 `--queries` 必须按 Pexels id 去重**：同一张图会被多个查询同时返回，旧代码只按 md5 查历史台账、不查本轮已选，结果同一张图进图集两次。已在合并阶段加 `seen_ids`，挑选循环加 `picked_ids`。
- **`--title` 可强制指定 news 标题**：`make_title()` 调模型失败时会静默退回「{话题}｜一眼心动的风景」模板，用户明确嫌这种 AI 味。生成失败或要指定时直接传 `--title`。
- **有效新图不足 9 张时脚本仍会建稿**（`MIN_VALID_IMAGES=5`）。要满 9 张就加查询路线（长江用 5 路：`yangtze river china` / `three gorges yangtze` / `chongqing skyline river` / `yangtze river gorge` / `three gorges dam`）。只有 7 张的稿子用户不要：删草稿后必须把本轮 md5 从 `logs/gallery_sent_md5.json` 的 `md5s` 和 `list` 里一起移除，否则重跑会全被判重、永远凑不满。
- Pexels 上中国的阿勒泰冬季实景可用，搜 `altay xinjiang snow` / `xinjiang snow`，alt 会标 `Altay Prefecture, Xinjiang`，比俄属阿尔泰的图更贴题。
- **稀缺题材凑不满 9 张时**：先用 `pexels_search(q, per_page=80)` 把该题材深翻一遍，再按 `alt` 里的地名字符串过滤，能捞出台账外的真图（梅里雪山最终拿到 8 张新图 + 2 张旧图候选）。不要**自行**拿邻近题材顶替，也不要静默交 7-8 张；确需换题或混源，先说明代价让用户拍板（他明确说“就用 Pexels”时照做，但回执要标明不是实拍该地点）。
- **草稿已建、只差第 9 张时走 `draft/update`，别整篇重跑**：`uploadimg` 上传缺的那张 → `draft/get` 取 `content` → 在 `<p><a data-miniprogram` 之前插入 `<p><img src="..." style="width:100%;"/></p><p><br/></p>` → `draft/update`，body 为 `{"media_id": ..., "index": 0, "articles": {...}}`，articles 复用 draft/get 返回的 title/author/digest/content_source_url/thumb_media_id/need_open_comment/only_fans_can_comment。整篇重建要 8-10 分钟，update 约 1 分钟。
- **手工补的图要单独补云转存**：`cloud_stash()` 只处理脚本自己那一批；补图后造一个临时目录（`full_1.jpg` = 处理图、`final_1.jpg` = 压缩图）再调一次，否则会出现草稿 9 张、云库 8 条。
- **补的是复用旧图或邻近题材图时，在回执里说明**（例：“第 9 张用了同一座山的旧图补位”），别让用户以为是新图。

### 跨源混编与题材真实性（2026-11）

- **用户临时指定张数时只传 `--count`**：12 张、18 张、20 张都走命令行，不改脚本默认值（9），否则后续定时任务与手动跑会分叉。20 张要传 40 次图（正文 + 封面 + 云转存），实测 10–15 分钟，**一律后台跑 + `notify`**，别用 420s 前台超时硬等。
- **Pexels 没有某地实景时，先如实说，再按用户决定做**：搜出来的同名结果是别处的（洞庭湖返西班牙/越南湖、岳阳楼返雷峰塔）。用户若坚持“就用 Pexels”，照做，但必须 ①在回执里明确“这期大部分是同题材湖景/山景，不是实拍该地点”，②把手里真实的少量本地图掺进去并标明来源。不要默默把泛图当实景发。
- **混源成稿用 `draft/update` 追加，不重跑主流程**：Pexels 那批用脚本建稿，Commons/自备图用 `uploadimg` 补到链接块之前，一条稿子可以同时含两种来源；补完记得给手工图单独补云转存，并在正文末尾加 CC 署名行（见 `references/image-sources.md`）。
- **题材真实性优先于凑数**：宁可交 8 张真实实景，也不要把邻近景点或别国的湖冒充成目标地点；要凑满就先跟用户说清代价，由他拍板（他可能同意换泛题，也可能同意署名放宽图源）。

### 话题池构成（2026-10-03）
- 77 条纯自然风景（山水/花草/树木/冰雪/沙漠/湖海，建筑·城市·人文·节庆已全数剔除）
- **+37 条动物**（非洲象、长颈鹿、雪豹、大熊猫、北极熊、座头鲸、火烈鸟群、丹顶鹤、企鹅群、发光水母……）→ **共 114 条**
- 动物的英文查询都带风景/光线词（如 `lion savanna golden light`、`horses galloping beach sunset`），避免搜出动物园特写。

### 新增脚本
- `scripts/prune_drafts.py`：**草稿箱清理**（2026-10-03 起）。删 N 天前的草稿并把图集对应话题从 `topics.json` + 脚本内置表**同步永久摘掉**（用户 2026-10-03 明确要永久删，不要冷却/回收）；默认 `--days 2`。另有 `--dry-run`、`--include-articles`。
  - cron job `e11f232f4c79`「草稿箱清理-每天09:00（图集+文章）」→ 包一层 `~/.hermes/scripts/prune_gzh_drafts.sh`，`no_agent=true`，stdout 即投递内容。包装脚本用的是 `--days 2 --include-articles`（文章日更 job 已停，文章一并清）。
  - **每次都会播报池子余量**（`pool_status()`）：`话题池剩 N 个关键词（…还能撑约 X 天）`，低于 40 条加 ⚠️ 提醒。用户要求**不要自动补词**，需要时他自己会提。
  - ⚠️ **已知代价**：图集 job 每小时 1 条 = 每天淘汰约 24 个关键词，171 条约 **7 天见底**；见底后靠 `_SEED_TOPIC` 兜底不会崩，但会反复出同一个题材。用户已知晓并接受。
  - `sync_pool()` 会同时给 `topics.json` 和 `pexels_gallery_draft.py` 各留一份 `.bak-<时间戳>` —— 只还原一个会造成两源不一致（踩过）。
- `scripts/prep_gzh_images.py`：Pexels 抓图 → 封面 2.35:1(940×400) + 正文图 16:9(1080×608)，带暗/亮像素自检（防过曝废图）。
- 图源与封面相关脚本：`scripts/commons_fetch.py`（Commons 批量下载 + 处理 + QC，走代理）、`scripts/commons_to_draft.py`（Commons 图直接建 news 草稿，可带署名行）、`scripts/cover_card6.py`（六格卡片，`--no-text` 出纯图）、`scripts/cover_card6_v2/v3/v4.py`（六格改进：色相排序 / 地平线对齐 / Reinhard 色彩迁移）、`scripts/cover_layout.py`（`--layout grid|main3|three`）。
- `scripts/verify_gzh_draft.py`：用 `draft/batchget` 验证草稿（title / 封面非空 / 正文 `<img>`≥1 / `<li>`=0），**必须 `r.content.decode("utf-8")`**（直接 `r.json()`/`r.text` 会中文乱码）。
- `scripts/delete_draft.py <media_id>`：删草稿（改稿后换新版时用）。**坑：报 `53407 定时发布中，无法删除或修改`** = 该草稿已在公众号后台被设为定时群发，API 动不了；此时不要建重复稿，让用户去后台取消定时后再说。

## 能力边界与限制
- **群发/发表 API 无权限**：`freepublish/submit`、`freepublish/batchget`、`message/mass/*` 在本号一律 `48001`（未认证订阅号没有群发接口）。要“自动发布”只能走后台网页的「定时发表」，或升级认证服务号。只读探测法、扫码登录接口（可直接拿到 472×472 二维码图发用户）见 `references/auto-publish.md`。**永远不要用 `freepublish/submit` 试探权限**——一旦有权限，那就是真的群发。
- **图片大小**：微信素材图片上限 **2MB**（超了报 `40006`/`45001`）。封面建议压缩 ≤800KB；正文图也需 ≤2MB。
- **文章长度**：微信草稿正文无硬性字数上限，建议单篇 ≤5 万字。
- **草稿更新**：`create_draft.py` 不支持更新已有草稿；改内容用新标题重建草稿 → `draft/delete` 删旧草稿（`freepublish/delete` 可能报 48001 未授权，回退旧接口）。

## 重试与故障排查
| 错误 | 含义 | 处理 |
|---|---|---|
| 40006 / 45001 | 图片超过 2MB | 压缩封面（≤800KB）/正文图（≤2MB） |
| 40007 | thumb_media_id 无效 | 确认封面上传成功返回的 media_id |
| 40125 | invalid appsecret（获取 access_token 失败） | AppSecret 已失效——公众号后台「设置与开发→基本配置→开发者密码」被**重置**过（旧值立即作废），或 .env 里的值被写坏。让用户在后台重置一次 AppSecret，拿到新值后更新 .env。**注意**：此错会表现为"全部图片素材上传失败"（每张图都要先换 token），别误判成图片/网络问题 |
| 48001 | 接口未授权 | 回退用旧接口（如 `draft/delete` 而非 `freepublish/delete`）。**若 `freepublish/*` 或 `message/mass/*` 报 48001，是这个号根本没有群发权限，换接口没用**，别反复重试 |
| no_cover | 未传封面 | 公众号草稿强制要求封面，先上传封面拿 media_id |

> ⚠️ **排错别只看 cron 摘要（已踩坑）**：`no_agent` 脚本若用 `tail -5` 汇报，会把 40125 之类的真实原因丢掉，只剩"全部图片素材上传失败"，白查半天。**脚本必须把完整 stdout+stderr 落盘**（如 `~/.hermes/logs/cron/gallery_<ts>.log`），stdout 只留一行摘要，并对 `40125 / invalid appsecret` 单独分流提示。
> 排 cron 失败的第一落点：`~/.hermes/cron/output/<job_id>/` 最新一个 `.md`（stdout 摘要）+ 脚本自己落的完整日志 `~/.hermes/logs/cron/*.log`（真实栈）。`cronjob list` 的 `last_error` 只留最后几行，遇到 `Script exited with code N` 必须去翻这两处，别拿摘要猜根因。
> 停/启用前先 `list`：`enabled=false / state=paused` 的 job 再 `pause` 是幂等的，可以放心重复；用户说「停掉某个任务」时先按名字和最近的 `last_run_at` 认准 job_id，别按记忆里的 ID 动手。

> ⚠️ **先按 `last_status` 分类，再决定查什么**：`error` = 脚本非零退出，去看 `last_error` 末几行 + 脚本完整日志（`~/.hermes/logs/cron/*.log`）；`delivery_failed` = 脚本本身跑成功，只是结果没推到微信（典型 `iLink sendmessage session not ready: ret=-2 ... the user must send the bot a message first`），**不要**去查 Pexels、磁盘或凭证，那是投递链路问题；`ok` 但用户没收到消息也先按投递算。用户问“最近任务怎么失败了”时，先把这两类分开再翻日志，否则会把推送失败误判成流水线故障。

> ⚠️ **凭证可能中途失效**：同一 AppSecret 可以在几分钟内从可用变为 40125（后台被重置）。判定"是不是凭证问题"最快的办法：直接 `GET /cgi-bin/token` 看 errcode，别先怀疑图或网络。

## 铁律
- 封面图 **必须有**，否则微信拒收草稿。
- **封面默认纯图不带字**（文字交给封面库/标题字段；要叠字先确认）。图集封面同样**不加任何文字**，只做多图竖拼（见「图集封面：多图竖拼」）。
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
- **把流水线交给用户带走时**：打一个 zip 包含 `scripts/pexels_gallery_draft.py + compress_image.py + config.py + retry_util.py`、两套话题池与 `topic_bank.json`、两个 cron 包装脚本、`SKILL.md`，以及 `README.md`（依赖含 numpy、两种模式对照表、常用参数、已知坑）和 `env.example`。**不要把真实 `.env` 打包或发到聊天里**（只有 AppID/AppSecret，发了等于泄密钥）；给模板并说明填法即可。
- 写作参考：`history-social-writing`、`news-social-writing`。

---

# 图集草稿流水线（pexels_gallery_draft.py）

## 概述

每小时/每 30 分钟产出一期公众号图集草稿：Pexels 抓图 → 翻转+滤镜 → 两版产出 → 传封面+正文图 → 建**图文消息(news)**草稿（正文末尾带可点击的小程序文字链）→ 同步小程序云存储。

> ⚠️ **要小程序链接就只能用 `news`（硬性）**：`newspic` 正文只支持纯文本，写 `#小程序://` 或 `<a>` 发布后都是死文字（HTML 还会报 45166）。两种模式都是设计内产出（见下方「图集脚本双模式」）：`news` = 图文消息 + 可点击链接，`newspic` = 纯贴图无正文；按任务选，别把 newspic 当“错误类型”。

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
- **2026-10-03 二次筛选（用户要求）**：181 → **77 条纯自然风景**。用户口径：*只留风景（山水/花草/树木/冰雪/沙漠/湖海），建筑/城市/人文/节庆一律去掉*。摘掉 94 条：教堂神庙宫殿城堡、桥楼塔场馆、古镇村落街巷、园林寺庙牌坊、人文节庆、城市地标。备份：`topics.json.bak-<时间戳>`。
- **2026-10-03 +37 条动物（用户主动要求加回）**：非洲象、长颈鹿、雪豹、大熊猫、北极熊、座头鲸、火烈鸟群、丹顶鹤、企鹅群、发光水母……→ **共 114 条**。动物的英文查询都带风景/光线词（`lion savanna golden light`、`horses galloping beach sunset`、`deer herd meadow morning mist`），避免搜出动物园特写。
- **2026-10-03 +34 条同类型扩展**（用户要求）：梯田晨雾、海岸悬崖、薰衣草田、白桦林、草原晨光、雪山日落、雨林溪流、芦苇荡、火山熔岩、盐湖倒影、高山杜鹃、瀑布群落、极光雪原、雾漫山峦、秋日枫林、海蚀地貌、湿地候鸟、沙漠胡杨、黄河九曲/壶口/入海、长城日落、黄山云海、桂林山水、武隆天生桥、雅鲁藏布、青海湖、喀纳斯湖、额济纳胡杨、扎龙湿地、呼伦贝尔草原、那拉提草原、巴音布鲁克、伊犁杏花 → **共 125 条**。
  - 新增词全部是自然风景（山水/花草/树木/冰雪/沙漠/湖海），没有建筑/人文。黄河系列和长城是特意补的——国内"大江大河"类之前一个都没有。
  - 扩展方式：直接往 `topics.json` 追加，再用 `pexels_gallery_draft.py` 的内置表同步（按中文序自动插位，两源必须一致）。
- 保留：自然风景 + 动物。建筑、城市、人文、节庆、美食、肖像等已全部剔除。
- **题材黑名单（长期有效，用户口径固定）**：梯田，以及沟壑 / 峡谷 / 戈壁 / 荒漠 / 雅丹 / 土林 / 荒芜 / 废墟这类荒凉、灰暗、缺乏美感的地貌，一律不要。判词按**子串**匹配（「峡谷」要能命中「雅鲁藏布大峡谷」），不能只比中文名全等。
- ⚠️ **删题材必须同时动五处，漏任一处都会被回填（硬性）**：
  1. `scripts/topics.json`（贴图 `newspic` 默认池）
  2. `scripts/topics_stunning.json`（图集 `news` 池，cron 用 `GALLERY_TOPICS_FILE` 指向它）
  3. `scripts/topic_bank.json` 的 `pending`（3 天轮换的补池来源，不清就会补回来）
  4. `pexels_gallery_draft.py`：`BANNED_TOPIC_WORDS` + `topic_allowed()`；`load_topics()` 对**池文件和 `_BUILTIN_TOPICS` 兜底表都要过滤**，内置表里的同类条目顺手删掉
  5. `rotate_topics.py`：候选循环里 `topic_banned()` 命中直接 append 到 `rejected` 并 `continue`，别只停在读池过滤——否则每次轮换都会重新尝试这些词
- 三个 JSON 改动前先各留 `.bak-ban<时间戳>`；改完按这个顺序自检，别只看肉眼：三个文件断言禁用词命中为 0 → `py_compile` 两个脚本 → 动态 `load_topics()` 打印池条数且命中为 0 → `rotate_topics.py --status` 正常。
- 「沟」字不是一律判死：官鹅沟、果子沟这类有水的景区保留，纯荒沟/沟壑才删；改动前把候选清单列给用户过目更稳。
- ⚠️ **池子消耗速度**：图集 job 每小时 1 条 = 每天约 24 条，125 条约 **5 天见底**。见底后靠 `_SEED_TOPIC` 兜底不崩，但会反复出同一个题材。用户明确**不要自动补词**，需要时他自己提；`prune_drafts.py` 的 `pool_status()` 每次清理都会播报剩余量和倒计时，低于 40 条加 ⚠️。

## 图片处理

> 图源：主源 Pexels；免费备选 **Wikimedia Commons**（CC0/PD 免署名，CC BY 系列要署名）的接入配方、代理要求和实测素材量见 `references/image-sources.md`。

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

- **写文章（run_pipeline）也要带小程序链接时**：在 `article.md` 末尾直接写同一段 raw HTML（`<p><a data-miniprogram-appid="..." ...>文案</a></p>`），markdown→HTML 会原样保留；建稿后用 `draft/get` 确认 `data-miniprogram-appid` 还在（实测保留）。别指望在 md 里写 `#小程序://` 或普通 `[文字](链接)`。

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
