---
name: "wanx-comic-captions"
description: "用通义万相生成治愈漫画并按模板用站酷快乐体配字"
---

# 通义万相漫画生成 + 站酷快乐体配字 Skill

## 用途
用阿里云 DashScope 通义万相（wanx2.1）文生图接口生成「治愈系对比漫画」（竖版上下两格），并用 Python Pillow + 站酷快乐体字体给上下格各配一句白色文字（浅橘粉描边+柔和阴影，每格顶部偏左）。可单张或批量生产。

## 前置环境
- 已有 DashScope API Key（`~/.openclaw/openclaw.json` 里 `dashscope` provider 的 `apiKey` 字段）。脚本需真实读取，勿手动粘贴脱敏 key。
- Python 3 + Pillow（`PIL`，>=10）。
- 站酷快乐体字体文件 `zk.woff2`（ZCOOL KuaiLe）。
- 网络可访问 `dashscope.aliyuncs.com`。

## 关键经验 / 坑（重要）
1. **API Key 不要硬编码脱敏字符串**：直接 `openclaw.json` 解析出真实的 `apiKey`（baseUrl 含 `dashscope` 且含 apiKey 的那个 provider 节点），否则会因省略号等字符导致 `UnicodeEncodeError: latin-1`。
2. **竖版尺寸**：通义万相 wanx 宽高限制 **512–1440**。竖版双格请用 `1024*1440`（`1024*1536` 会报 `InvalidParameter: Either width or height should be between 512 and 1440`）。
3. **wanx 是异步任务**：提交返回 `task_id`（`X-DashScope-Async: enable`），需轮询 `GET https://dashscope.aliyuncs.com/api/v1/tasks/{id}` 直到 `task_status==SUCCEEDED`，再取 `output.results[0].url` 下载。
4. **dashscope 官方绘图端点**：`POST https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis`（不是 chat 端点）。模型用 `wanx2.1-t2i-turbo`。参数：`{"size":"1024*1440","n":1,"prompt_extend":True}`。
5. **外部字体源大多被墙**：raw.githubusercontent.com / github.com / ghproxy 全都不通。可用：`gitee.com`、`unpkg.com`、`jsdelivr`。
   - 站酷快乐体可用：`https://unpkg.com/@fontsource/zcool-kuaile@latest/files/zcool-kuaile-5-400-normal.woff2`（fontsource 分片，实测覆盖常用汉字，够用；若有缺字再下其它分片）。
6. **Pillow 支持直接加载 woff2**：`ImageFont.truetype("zk.woff2", size)` 可用，无需转 ttf。

## 推荐的漫画提示词模板（治愈系对比，竖版双格）
```
竖版9:16治愈系手绘漫画，上下两格构图，从上到下排列，构成'抱怨 vs 感恩'的对比叙事。
主角是一个顶着绿色豆芽芽、穿橙色背带裤的圆润蛋形小生物，表情可爱有辨识度。
上格（抱怨）：<抱怨的画面描述>，画面偏灰蓝冷色调。
下格（感恩）：<感恩的画面描述>，画面转为明亮暖色调。
整体：扁平简约手绘线条、柔和配色、留白充足、上下两格之间自然分隔。传达'换个角度看，平凡生活也有幸福'的治愈主题。画面干净、温馨、萌系。
```

## 工作流
1. 从 `openclaw.json` 解析真实 DashScope key，提交 wanx 文生图任务（1024*1440）。
2. 轮询任务直至成功，下载 PNG 到临时目录。
3. 用 Pillow + 站酷快乐体在上下格各画一句白色文字：
   - 字体大小 `W*0.075`（小一号，秀气）
   - 描边 `stroke_width = max(1, fs*0.04)`，描边色浅橘粉 `(220,150,120,255)`
   - 先画柔和阴影（偏移 `+stroke_w,+stroke_w*2`，色 `(255,180,150,110)`）再画正文
   - 正文纯白 `(255,255,255,255)`
   - 位置：每格顶部偏左；上格 text 顶部 `H*0.05`，下格 `H*0.56`，左边距 `W*0.06`
4. 输出带文字的 PNG 交付。

## 参考脚本
根目录 `scripts/` 下：
- `wanx_gen.py`：文生图（提交+轮询+下载）
- `add_captions.py`：给上下格配字（参数：图片、输出、上格文字、下格文字、可选字号比例）
