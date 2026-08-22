# Auto Skills

个人 Agent(OpenClaw)技能库合集,自动同步自 `~/.openclaw/workspace/skills/`。

## 内容

覆盖:
- 公众号写作流水线(历史 / 新闻类,含 AI 味终检闭环)
- 微信发布、腾讯文档、内容抓取、新媒体运营
- 深度研究、Agent 运维排障、图像生成等

## 使用

技能目录直接放入 Agent 的 skills 目录即可被识别:

```bash
# 以 history-social-writing 为例
cp -r skills/history-social-writing ~/.openclaw/workspace/skills/
```

## 安全说明

- 所有密钥(微信公众号、DashScope 等)一律从环境变量或 `~/.openclaw/openclaw.json` 读取,不入库。
- 仓库内 `*.env.example` 仅为字段模板,无真实值。
