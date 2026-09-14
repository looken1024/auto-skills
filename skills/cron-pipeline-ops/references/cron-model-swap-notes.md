# 换 cron 任务模型 & 整链失效判定（2026-09-14/15 实战）

## 场景
公众号文章日更（job 4b552ab71572）原 pin `dots-studio/dots-3-note-preview:free` @ cline_local，用户要求换成当前会话同款 `z-ai/glm-5.3-flash` @ custom_cline。手动触发验证 → 整链失败。

## 换模型的实操
1. **cronjob 工具接口不支持改 model 字段**（update 只收 prompt/schedule 等），`hermes cron edit --provider` 又不校验 provider 名。可靠路径：直接改 `~/.hermes/cron/jobs.json` 里该 job 的 `model`/`provider` 字段（Python json 读写，别手编）。
2. 改完**双确认**：① 回读 jobs.json；② cronjob(action='list') 看运行时视图。两边一致才算落盘。
3. prompt 里写明模型绑定 + 限流条款（429 等 60s 重试一次，仍失败发邮件终止，禁止自行换模型）——用户的规矩：换模型必须经他同意。

## 整链失效的根因判定
手动跑后报 `RuntimeError: HTTP 500 ... failed to invoke model 'google/gemma-4-31b-it:free' ... 429`（注意：**错误原文里的模型是 fallback 链最后一级**，不代表主模型状态）。

判定步骤（裸 curl 直连上游，key 从 `~/.hermes/.env` 读）：
```python
import json, urllib.request
key = [l.split('=',1)[1].strip() for l in open('/home/ubuntu/.hermes/.env') if l.startswith('CUSTOM_CLINE_API_KEY=')][0]
for m in ["z-ai/glm-5.3-flash", "google/gemma-4-31b-it:free"]:
    req = urllib.request.Request('https://api.cline.bot/api/v1/chat/completions',
        data=json.dumps({"model":m,"messages":[{"role":"user","content":"回复两个字：在线"}],"max_tokens":10}).encode(),
        headers={"Authorization":"Bearer "+key,"Content-Type":"application/json"})
    try:
        r = json.load(urllib.request.urlopen(req, timeout=60))
        print(m, "->", r.get('data',r)['choices'][0]['message']['content'])  # cline 会包壳 data
    except Exception as e:
        print(m, "->", str(e)[:120])
```

当日实测结论：
- `z-ai/glm-5.3-flash`：连续 2 次 HTTP 500（上游模型坏），但**交互会话里正常**——同一模型不同调用路径可用性不同，聊天能用≠cron 能用。
- `google/gemma-4-31b-it:free`：失败当时 429，几小时后重测 200 正常（注意 cline 响应是 `data.choices` 包壳，取值要 `r['data']['choices']`）。
- **免费池抖动是小时级**：先等 60s 重测一次，通了就是瞬时抖动别改配置；连续多测仍坏才动模型。
- fallback 链全挂 = 主模型 + 所有备胎同时坏，属上游事件；向用户汇报时给实测证据，别猜。

## 后续
- 该 job 已 pin glm-5.3-flash；若次日晚班（23:00）再 500，考虑换回 dots-3-note-preview（需用户同意）。
- 检查 fallback 链位置是否合理（gemma-4-31b 当时在末位）。
