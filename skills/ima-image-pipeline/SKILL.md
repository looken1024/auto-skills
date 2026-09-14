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

### Step 2 润色提示词（主路径：关键词+风格后缀，不依赖 LLM）

**主路径（实测稳定，2026-09-15）**：直接把话题池的英文关键词 + 固定风格后缀拼成提示词，**不调用任何 LLM**。cline 免费池（gemma-4-26b / glm-5.3-flash / cohere / gemma-4-31b）在本机整链失效是常态（404/429/500 交替出现），把出图链路绑在免费模型上等于每次都要赌上游恢复。关键词本身已是英文、已是具体场景词，加一句风格描述就够用：

```python
SUFFIX = "photorealistic, atmospheric, portrait orientation, soft natural lighting, high detail, no text, no watermark, no signature, no logo, no people"
prompt = f"{kw['en']}, {SUFFIX}"
```

- 风格：photorealistic / 氛围感 / 适合公众号封面
- 尺寸：竖版 576×1024（pollinations 竖版硬上限）
- 一句话，不超过 60 英文词
- 禁止人名、logo、文字、水印（后缀里写死）

**可选增强路径**：如果 cline 池可用，可调免费模型把 cn 关键词润色成更生动的英文提示词再出图。但**主路径必须能在零 LLM 依赖下跑通**——这是流水线稳定性的底线。

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

## 踩坑实录（2026-09-15 实测，每次跑流水线前先读一遍）

### 1. pollinations 下载：urllib 403，必须 curl + UA
```python
# ❌ urllib.request.urlretrieve 会 403
# ✅ curl -A Mozilla/5.0 就通
subprocess.run(['curl','-sL','-A','Mozilla/5.0','-o',out,url], capture_output=True, timeout=180)
```
别靠 HTTP 状态码判断——curl 返回 0 但文件可能是空的或 HTML 错误页。

### 2. cline 免费池整链失效是常态
| 模型 | 当日实测 |
|---|---|
| `google/gemma-4-26b-it:free` | 404 |
| `z-ai/glm-5.3-flash` | 429 |
| `google/gemma-4-31b-it:free` | 包壳无 choices |
| `cohere/north-mini-code:free` | 500 |

**不要把出图链路绑在免费模型上。** 主路径（关键词+风格后缀）零 LLM 依赖，这才是稳定性的底线。如果非要 LLM 润色，先裸 curl 探活，通了再用。

### 3. IMA 笔记的图片引用会被丢
`import_doc` 写入的 `![alt](https://res-pkb.ima.qq.com/...)` 网络图片引用，回读 `get_doc_content` 时会被去掉，只剩纯文本。图片本身在知识库里完好。**笔记里目前看不到图**——要显示只能在 IMA 客户端里手动插图。

### 4. COS 凭证 key 名是下划线
`create_media` 返回的 `cos_credential` 里是 `secret_key`（下划线），不是 `secret-key`。

### 5. IMA API 路径
笔记 `openapi/note/v1/...`，知识库 `openapi/wiki/v1/...`。**不要用 `openapi/list_docs`**（404）。
