# 内容流水线的配图素材来源（免 key 路线，2026-09-13 实测）

适用：公众号封面/正文图、图集、短视频封面。前提是**不假设 DashScope key 存在**。

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

## B. pollinations 免费生图（无 key）

`https://image.pollinations.ai/prompt/<urlencoded 英文提示词>?width=512&height=512`

- 免 key；竖版硬上限 **576×1024**（要更大只能裁/放或另找源）。
- 成品右下角常带水印，裁掉底部约 **52px**（`im.crop((0, 0, w, h - 52))`）即可。
- 写实风提示词加 `photorealistic, natural lighting, no text, no watermark`；要 16:9 用 `?width=1024&height=576` 再等比裁。

## C. 一律要过看图验证（硬性）

- 明暗自检只能判“过暗废图”（`dark = sum(hist[:85])/total*100 > 90` → 重生成）；**全亮不等于废图**，必须看图。
- 图片存在**文字/水印**（如 "头条@xxx"）要先裁掉或换图；裁前让视觉确认主体坐标与安全范围，别裁到人物。
- 没有 DashScope key 时，直接用 agent 自带视觉看本地文件（`vision_analyze(image_url='/tmp/cover.jpg', question='画面是什么？有文字水印吗？适不适合配 X 题材？')`）——同样能判废图、水印、主体与题材是否相符，不需要 key。
- 别凭网页文字描述推断网络图内容（曾把报道配图认错发进草稿箱）。
