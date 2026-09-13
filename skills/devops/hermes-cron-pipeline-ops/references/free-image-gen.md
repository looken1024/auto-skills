# 免 key 出图：pollinations.ai（2026-09-13 本机实测）

要“按提示词出图”但**没有 DashScope/千问 key**（本机 `.env` 无 `DASHSCOPE_API_KEY`，`wechat-ai-publisher` 里那套 `openclaw.json` 路径在本机不存在）时的备选。

## 用法（GET 直出，无需 key/登录）

```bash
curl -s -o /tmp/out.jpg -m 60 \
  "https://image.pollinations.ai/prompt/<URL-encoded prompt>?width=512&height=512&nologo=true"
```

- 实测：`200`，`image/jpeg`，512×512，**3.7s** 返回真实 JPEG（约 34KB），无重试无 key
- 参数：`width` / `height`、`nologo=true`（仍可能带小角标）、可选 `seed=` / `model=`
- 提示词用英文更稳；URL 里必须 encode（空格→`%20`）

## 出图后必做（与千问同规矩）

1. PIL 判废图：`dark = sum(hist[:85])/total*100`，>90% 过暗作废；**全亮不要急着判废**，先看图。
2. 视觉模型（`vision_analyze` 或 `qwen-vl-max`）确认：主体是否符合用途、**有无文字/水印**（默认右下角有小角标，要交付就裁掉或重出）。
3. 发给用户时用平台 MEDIA 语法直接附图。

## Cloudflare 站点别耗时间

`perchance.org`（含 `ai-character-generator`、`image-generation.perchance.org/api/*`）对本机出口 IP 一律 Cloudflare 挑战（403 / `Just a moment...`）；换 mihomo 节点、Xvfb 有头浏览器都没过（详 SKILL.md 第 5 节）。**直接换免 key 的 pollinations**；用户在本地住宅网络打开 perchance 没问题（那个站免登录）。

> 另：`perchance.org/ai-character-generator` 本身是**角色设定文本生成器**；perchance 真正按提示词出图的是 `perchance.org/ai-text-to-image-generator`——用户可能把两者记混。
