# 发布前终审改走 API + 平台登录态恢复（2026-10-20 实战）

## 1. 网页版终审是硬单点
微头条流水线原来在发布前调用 `ds_web_review.py`（裸 CDP 驱动 chat.deepseek.com）。
DeepSeek 网页登录态一掉，脚本返回 `{"ok": false, "error": "...未登录（跳到 sign_in）"}`，
`wt_pipeline.sh` 按策略直接 **停发** —— 整条流水线每小时跑一遍、每小时都发不出去。

**结论：凡是“发布前必须过”的闸门，不要依赖网页版登录态。** 网页版可以留给人工复盘/交叉验证，闸门本身要走 API。

## 2. 改法：同一个提示词，换 API 通道
新增 `wt_review_api.py`：
- `from ds_web_review import PROMPT_TMPL` 复用原提示词（判定口径不变）
- `from wt_common import llm` 走主模型
- 输出契约保持 `{"ok":true,"verdict":"PASS|FIX","model":...,"answer_chars":N}`，并落盘答案文件
- `wt_pipeline.sh` 里两处 `ds_web_review.py` 调用（首次终审 + 每轮改后复审）一起替换

## 3. reasoning 模型的关键参数（踩过）
`deepseek-v4.1-flash`（opencode-go）在约 1.2 万字符的终审 prompt 上：

| max_tokens | 结果 |
|---|---|
| 8000（当时的 eff_cap） | `content` 为空 → 脚本判“空回复”，fallback 到免费模型 |
| 12000 | 稳定返回 1100+ 字正文，约 55s |

必须同时满足：`stream=False` + `reasoning_effort="low"` + `max_tokens>=12000`（长 prompt）。
短探活 500-2000 足够；**长输入要按 reasoning 开销重新给额度**，否则看起来像“模型没返回”。

## 4. 多模型链要按模型切端点
`wt_common.llm()` 的 `MODEL_CHAIN` 第一项是主模型，后面是免费兜底；不同模型属于不同 provider，不能共用一个 endpoint：

```python
use_opencode = m in OPENCODE_MODELS
endpoint = OPENCODE_URL if use_opencode else PROXY   # opencode vs 本地 8899 解包代理
hdrs = {"Authorization": f"Bearer {_opencode_key() if use_opencode else _api_key()}"}
if use_opencode:
    hdrs["x-opencode-session"] = "hermes-main"
```

## 5. 平台登录态：先验旧 cookie，再让人扫码
头条（mp.toutiao.com）的 `sessionid` / `sessionid_ss` 存在
`~/.hermes/skills/toutiao-micro-publish/config/toutiao_cookies.json`。

**不要因为“用户以前发过”就直接说需要重发** —— 先注入验证：
```bash
python3 ~/.hermes/cache/inject_toutiao_cookie.py --verify
# 输出“仍然跳到登录页 —— sessionid 已失效”才算真过期
```
实测 9 月 13 日的 sessionid 到 10 月 20 日已失效（约 5 周）。

## 6. 从无头 Chrome 取登录二维码给用户扫
登录页二维码是 `data:image/png;base64,...` 的 `<img>`，可直接抠出来，不必截整页：

1. 新开/复用 `mp.toutiao.com` 标签页，`Page.navigate` 到 `https://mp.toutiao.com/`
2. 点“扫码登录” tab
3. 取最大的一张 data:image：

```js
(() => {
  const imgs=[...document.querySelectorAll('img')].filter(e=>e.src&&e.src.startsWith('data:image'));
  if(!imgs.length) return null;
  imgs.sort((a,b)=>b.naturalWidth*b.naturalHeight-a.naturalWidth*a.naturalHeight);
  return {src:imgs[0].src, w:imgs[0].naturalWidth, h:imgs[0].naturalHeight,
          expired:/二维码已失效/.test(document.body.innerText)};
})()
```

- 抠 base64 → 存 PNG（实测 512×512、13KB）→ 用 `MEDIA:` 发给用户
- 生成后**立刻发**：二维码几分钟失效；页面出现“二维码已失效点击刷新”就重新 navigate 再取
- 扫码后跑 `inject_toutiao_cookie.py --verify` 或一班 dry-run 确认登录态
