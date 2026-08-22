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
写作步骤可插拔：**通用版** `wechat-article-writer` 或 **人设版** `laoluo-article-writer`；历史/新闻社会类用 `history-social-writing` / `news-social-writing`（已内置参考文献铁律与标题三候选规范）。

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

## 能力边界与限制
- **图片大小**：微信素材图片上限 **2MB**（超了报 `40006`/`45001`）。封面建议压缩 ≤800KB；正文图也需 ≤2MB。
- **文章长度**：微信草稿正文无硬性字数上限，建议单篇 ≤5 万字。
- **草稿更新**：`create_draft.py` 不支持更新已有草稿；改内容用新标题重建草稿 → `draft/delete` 删旧草稿（`freepublish/delete` 可能报 48001 未授权，回退旧接口）。

## 重试与故障排查
| 错误 | 含义 | 处理 |
|---|---|---|
| 40006 / 45001 | 图片超过 2MB | 压缩封面（≤800KB）/正文图（≤2MB） |
| 40007 | thumb_media_id 无效 | 确认封面上传成功返回的 media_id |
| 48001 | 接口未授权 | 回退用旧接口（如 `draft/delete` 而非 `freepublish/delete`） |
| no_cover | 未传封面 | 公众号草稿强制要求封面，先上传封面拿 media_id |

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
