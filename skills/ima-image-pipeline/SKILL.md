---
name: "ima-image-pipeline"
description: "从公众号图集话题池选关键词→free模型写提示词→出图→上传IMA知识库+建笔记，每日自动跑。"
---

# IMA 图片流水线（ima-image-pipeline）

从 wechat-ai-publisher 图集话题池里挑关键词，用免费模型润色成出图提示词，生成图片，上传到 IMA 知识库并建一篇笔记引用它。每日自动跑。

## 触发场景
- "生成一张图放到IMA笔记里"
- "从图集话题里挑个词出张图"
- cron 定时任务（每日上午自动跑一轮）

## 工作流程（5 步）

### Step 1 选关键词

从 `~/.hermes/skills/wechat-ai-publisher/scripts/topics.json` 读话题池，随机抽 1 个 cn 关键词（排除已发过的，避免重复）。

### Step 2 润色提示词（free 模型）

用免费模型把关键词扩成英文出图提示词（pollinations 要求英文）。调用方式：
```bash
python3 -c "
from hermes_tools import web_search  # 复用现有工具链
"
```
或直接走 cline 免费池（`google/gemma-4-26b-it:free`，小上下文 prompt，限流就等 60 秒重试）。提示词要求：
- 风格：photorealistic / 氛围感 / 适合公众号封面
- 尺寸：竖版 576×1024（公众号封面常用竖图）
- 一句话，不超过 60 英文词
- 禁止人名、logo、文字、水印

### Step 3 生成图片

```bash
curl -sL -o /tmp/ima_img.jpg "https://image.pollinations.ai/prompt/<URL编码的prompt>?width=576&height=1024&nologo=true&seed=<随机>"
```

- pollinations 免 key，竖版上限 576×1024
- 生成后必须 `file` 验证是 JPEG 且尺寸正确；不是 → 重试或换 seed

### Step 4 上传 IMA 知识库

完整流程（4 个 GATE）：
1. `preflight-check.cjs --file <path>` → 拿 file_name/file_ext/file_size/media_type/content_type
2. `check_repeated_names` → 重名就改名加时间戳
3. `create_media` → 拿 media_id + cos_credential
4. `cos-upload.cjs` 上传 → 必须 exit 0
5. `add_knowledge` → 加到 `~/.hermes/skills/ima-skill/references/ima_kb.json` 里记的目标知识库

全部走裸 curl（不用 node ima_api.cjs，它对 list_docs 有 404 坑；note/wiki 接口路径正确）。

### Step 5 建笔记

```bash
POST https://ima.qq.com/openapi/note/v1/import_doc
{"content_format":1,"content":"# <标题>\n\n![<标题>](<get_media_info 返回的 url>)\n\n<描述>"}
```

- 笔记标题 = 图片文件名（不含扩展名）
- 内容里用 `get_media_info` 返回的 `url_info.url` 做图片引用
- 回读 `get_doc_content` 验证笔记落箱

## 调度
- cron：每日上午 09:45（错开图集趋势挖掘 09:40），agent 版，带 continuity
- GitHub 提交：改完主动跑 `bash ~/.hermes/scripts/skills_backup.sh`

## 红线
- 图片必须过 `file` 验证尺寸，不是 JPEG/尺寸不对就重试或换 seed
- 知识库固定用 `~/.hermes/skills/ima-skill/references/ima_kb.json` 里记的 kb_id（用户个人库），不许自己挑
- 不碰人名/logo/文字——提示词里必须写死 "no text, no watermark, no signature"
- 出图失败不要硬凑，报告失败并终止
