# 内容流水线的配图素材来源（免 key 路线）

适用：公众号封面/正文图、图集、短视频封面、**成对图（情侣头像等）**。前提是**不假设 DashScope key 存在**。

## A. Pexels 实拍照片（首选：真实、无 AI 味）

复用图集流水线已有的 helper 与同一个 key 配置：

```python
import sys, os
sys.path.insert(0, os.path.expanduser("~/.hermes/skills/wechat-ai-publisher/scripts"))
import pexels_gallery_draft as P   # key 从 ~/.hermes/skills/douyin-card-pipeline/config.json 读
photos = P.pexels_search("calendar desk planner", per_page=40)
P.pexels_fetch(photos[0]["id"], "/tmp/cover_raw.jpg")
```

- 关键词用「物件 + 环境」（calendar / desk lamp / office desk / clock / weekend）比抽象词命中率高。
- 封面按公众号头图 **2.35:1** 裁：`ImageOps.fit(im, (940, 400), Image.LANCZOS, centering=(0.5, 0.5))`；主体偏上时用 `centering=(0.5, 0.35)` 留天头。
- 实拍图常自带印刷文字（如日历上的 "Monthly Planner"）——属图内内容、非叠加标题，一般可用；但用户要求“封面不带任何文字”时必须换图。
- **免费额度 200 次/小时**。批量探活会吃掉额度，别在别处把额度用光。
- **“搜得到”≠“图对”**：地名/文物类英文词（尤其中国景点）会返回无关的近似图。必须看 `photos[].alt` 和 `photos[].url` 抽查，跑了偏就换词（`dong drum tower`→返北京鼓楼，改 `dong minority village guizhou` 才对）。Pexels 确实没有的词直接弃用，别硬凑。
- `per_page=15` 全部返回 15 只说明“≥15”，不代表池子真深；`per_page=8` 下 <8 条才算偏瘦。

## B. pollinations 免费生图（无 key）

`https://image.pollinations.ai/prompt/<urlencoded 英文提示词>?width=512&height=512`

- 免 key；竖版硬上限 **576×1024**。正方形请求 1024 实测只给 **768×768**；横版 `1024×512`、`1024×576` 可用。
- **水印必然存在**（`&nologo=true` 也不生效），在**右下角**。裁底部即可：768 高裁 **56px**、512 高裁 **44px**。
- 写实风提示词加 `photorealistic, natural lighting, no text, no watermark`；要 16:9 用 `?width=1024&height=576` 再等比裁。
- **限流很凶，约一半请求返回空文件**：不能靠 HTTP 状态码判断——`curl` 返回 0 但文件只有 2~5 字节（空/HTML 错误页）是常态。必须**重试 3~4 次 + 每次 sleep 5~10s**，并按“文件 >5KB 且 PIL 能打开”判定成功。
- **提示词约束力有限**：写 `flat 2D vector` 仍常出 3D；写“左半粉底右半蓝底”这类**分区背景基本不被遵守**。要分区/配色就自己用 PIL 后处理（见 D）。

### ⚠️ 下载方式：urllib 会 403，必须 curl + User-Agent（2026-09-15 实测）

```python
# ❌ 直接 urllib.request.urlretrieve 会 403 Forbidden
urllib.request.urlretrieve("https://image.pollinations.ai/prompt/...", out)

# ✅ curl 加 -A Mozilla/5.0 就通
subprocess.run(['curl', '-sL', '-A', 'Mozilla/5.0', '-o', out, url], capture_output=True, timeout=180)
```

## C. 一律要过看图验证（硬性）

- 明暗自检只能判“过暗废图”（`dark = sum(hist[:85])/total*100 > 90` → 重生成）；**全亮不等于废图**，必须看图。
- 图片存在**文字/水印**（如 "头条@xxx"）要先裁掉或换图；裁前让视觉确认主体坐标与安全范围，别裁到人物。
- 别凭网页文字描述推断网络图内容（曾把报道配图认错发进草稿箱）。

## D. 成对图 / 情侣头像：**一次生成整幅，再切开**

**不要分两次生成“另一半”**——两次生成的风格、清晰度、配色必然不齐（实测：粉色那张锐利 3D，蓝色那张发虚、只有头没有身体、还多一圈光晕），拼在一起一眼假。

已验证做法（2026-10-02 情侣头像）：

1. **一次生成含两个主体的横图**：`?width=1024&height=512`，提示词写 `exactly two ... looking at each other face to face`。
   - **朝向必须靠提示词**：只有明确写 `face to face / looking at each other` 才可能出面对面；**对正面/对称的角色做水平镜像没有意义**（翻转后还是正面）。
2. **裁水印**（底部 44px）。
3. **自己上配色**（生成器不听话时）：左半叠粉、右半叠蓝，`Image.blend(im, tint, 0.30)` —— 30% 混合既形成情侣配色又不糊掉细节。
4. **从正中间竖切** → 两半天然同画风、同清晰度，还自带“合起来才是一整幅”的拼图感。
5. **补成正方形 + 留安全边距**：每半先把内容缩到 **90%** 再居中贴回 512×512（背景取角像素），否则平台裁成圆形头像时会切到内侧的脸/胡须。
6. **自查圆形裁切**：PIL 画椭圆遮罩合成一张，`vision_analyze` 问“主体有没有被切掉”。

验收姿势：把两半**并排拼成一张预览**再喂 `vision_analyze`，问“朝向是否相反/画风与清晰度是否一致/有无水印/是否成对”。逐张单独问容易得到矛盾结论。

## E. 看图能力本身：`vision_analyze` 的后端接线（2026-10-02 修复）

**症状**：`vision_analyze` 报 `402 insufficient_credits`（余额指向第三方中转），看起来像“没有识图能力”。

**根因**：识图走 `auxiliary.vision`，`provider: auto` 时可能落到额度耗尽的第三方，而不是主模型。

**修法**（主模型本身支持读图时最省事）：

```bash
hermes config set auxiliary.vision.provider deepseek
hermes config set auxiliary.vision.model deepseek-flash
```

- ⚠️ **`~/.hermes/config.yaml` 受保护，agent 不能直接写**（write/patch 会被拒），必须走 `hermes config set`。
- 兜底写法（不想改配置时）：把图转 base64 拼成 `data:image/jpeg;base64,...` 塞进主模型 `chat/completions` 的 `image_url`。

**为什么优先修配置而不是一直用兜底**：`vision_analyze` 会把图**载入 agent 自己的上下文**，看得准；让外部模型“描述”再读描述，结论会前后矛盾（本次同一张图先被判“朝右”、再被判“朝左”“正前”），容易把不合格的成品判成合格。
