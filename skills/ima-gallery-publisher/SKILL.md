---
name: "ima-gallery-publisher"
description: "每小时扫描 IMA 新增的『每日图集』笔记，提取笔记内图片自动排版并发布到公众号草稿箱。"
---

# IMA 每日图集 → 公众号草稿（ima-gallery-publisher）

每小时扫描 IMA 笔记里新出现的「每日图集」笔记，提取笔记内的全部图片，压图、传素材、按统一模板排版，自动发布到公众号「棱镜折射」的草稿箱（不群发）。

## 触发场景
- "看看 IMA 有没有新图集，发个草稿"
- "把这篇图集笔记做成公众号图文"
- cron 定时任务（每小时第 20 分自动跑）

## 工作流程（6 步）

### Step 1 扫描新图集笔记

```bash
python3 ~/.hermes/skills/ima-gallery-publisher/scripts/scan_notes.py
```

- 调 IMA `openapi/note/v1/search_note`（search_type=0，query_info.title="每日图集"），拉取所有命中笔记
- 对照本 skill `data/published_notes.json` 台账（记录已处理的 note_id），只保留新增的
- 输出待处理清单：note_id + title；无新增则打印 `NO_NEW` 退出（cron 会静默）

### Step 2 提取图片（关键坑，已踩过）

```python
# ⚠️ 必须用 target_content_format=1（Markdown）拉正文，format=0 拿不到图片
# ⚠️ markdown 图片语法是 ![alt](url "title")，URL 和 title 之间有空格+引号
#    正则必须剥掉 title 后缀：r'!\[([^\]]*)\]\((\S+)(?:\s+"[^"]*")?\)'
# ⚠️ URL 里的 \\ 转义要去掉；直接 curl 下载（URL 含 emoji 无影响）
```

每张图下载后用 `file` 验证是 JPEG/PNG 且 >20KB，失败的跳过并记录。

### Step 3 压图 + 传素材

1. 每张用 `wechat-ai-publisher/scripts/compress_image.py --input X --output Y` 压到 300-600KB
2. 每张用 `wechat-ai-publisher/scripts/upload_material.py --image_path Y` 传到微信素材库，拿 `url`（正文用）
3. 第 1 张图再单独传一次，拿 `thumb_media_id`（封面用）

### Step 4 排版（固定模板）

结构：
- 开头居中引导区（主标题句 + 副标题句，从笔记标题和 summary 提取）
- 每张图一节：`<h3>` 风格名（红色 #8B0000 竖线装饰，文本取自图片 alt）+ 一句描述（可省略，没有就只放图）+ `<img>` 横版满幅圆角
- 结尾居中「— 完 —」

标题格式：`<主题> · 每日图集｜<副题>`，digest 取笔记 summary 第一句。

### Step 5 建草稿

```bash
python3 ~/.hermes/skills/wechat-ai-publisher/scripts/create_draft.py \
  --title "..." --digest "..." --author "棱镜折射" \
  --content "<html>" --thumb_media_id "..."
```

成功标志：返回 `status: success, errcode: 0`。然后用 `verify_draft.py` 验证：标题匹配 + 正文 img 数量 = 实际图片数。

### Step 6 记台账

把 note_id 追加进 `data/published_notes.json`（防重复发布）。跑完后 `bash ~/.hermes/skills/scripts/../../../scripts/skills_backup.sh` 推 GitHub（或直接 `bash ~/.hermes/scripts/skills_backup.sh`）。

## 调度

- cron：每小时第 20 分（`20 * * * *`），agent 版（需要处理异常和排版，不能 no_agent）
- 输出纪律：最终回复 ≤150 字（处理了哪篇、几张图、草稿 media_id、是否成功）；无新笔记回复 `[SILENT]`

## 红线
- 只处理标题含「每日图集」的笔记，其他不动
- 同一 note_id 只发一次，台账为准
- 图片下载失败超过一半（<50%）就终止本篇，报邮件不发残缺草稿
- 不群发，只存草稿（用户铁律）
