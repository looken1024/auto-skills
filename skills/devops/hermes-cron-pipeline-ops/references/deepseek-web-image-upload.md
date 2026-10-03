# DeepSeek 网页版上传图片 + 识图（实测可用）

2026-10-03 实测跑通全链路。同一套裸 CDP（`websocket-client` + `suppress_origin=True`，连 9222）既能跑 `ds_web_review.py` 之类的文本终审，**也能让网页版看图**——多一条识图通道，用于 API 识图不可用、或需要交叉验证时。

## 通道对比

| 通道 | 优 | 劣 |
|---|---|---|
| API（`vision_analyze` 钉到 deepseek） | 稳、快、可脚本化 | 走 token |
| **DeepSeek 网页版** | 免 API 额度 | 依赖登录态、要起浏览器、一次几分钟、会在账号里留聊天记录 |

## 三步配方

### 1. 上传：直接给 `input[type=file]` 喂文件

页面里就有隐藏的 `input[type=file]`（accept 覆盖 `.png/.jpg/.jpeg/.webp` 等）。

```python
cdp("DOM.enable")
root = cdp("DOM.getDocument")["root"]["nodeId"]
nid = cdp("DOM.querySelector", nodeId=root, selector="input[type=file]")["nodeId"]
cdp("DOM.setFileInputFiles", files=["/abs/path/to/img.jpg"], nodeId=nid)
```

**不用模拟点击**去开文件选择器，直接把路径塞给 input 最稳。
上传成功的判据：composer 里出现 `blob:` 缩略图（`img.src` 以 `blob:` 开头）。

### 2. 填字：React 受控 textarea，必须用 native setter

**直接 `ta.value = "..."` 不生效**（React 不认）。要拿原型链上的原生 setter 再派发 `input` 事件：

```javascript
(() => {
  const ta = document.querySelector('textarea');
  const set = Object.getOwnPropertyDescriptor(
      window.HTMLTextAreaElement.prototype, 'value').set;
  set.call(ta, '这张图里是什么？');
  ta.dispatchEvent(new Event('input', {bubbles: true}));
  return ta.value;
})()
```

### 3. 发送 + 读回复

- 发送：点 composer 区的主按钮（`ds-button--primary`）；有附件的状态下按钮可用性跟纯文本不同，先看它是否已启用
- 读回复：取**最后一个** `[class*="markdown"]` 容器的 `innerText`
- 判定出了新回答：发送前后各数一次 markdown 容器数量，数量增加即新回答

> ⚠️ 别用通用 `js()` 取正文——在 DeepSeek 页上会落到错的执行上下文（只拿到壳），这也是那些 review 脚本坚持用裸 CDP 的原因。

## 验证记录

上传一张 512×512 的粉色卡通老鼠头像 → 问「这张图里是什么？」→ 答 **“一只粉色圆滚滚的卡通小老鼠”**，答对，**不是敷衍式的“我看到了图片”**。确认它真能识图，而不只是接受了上传。

## 注意

- 会往用户的 DeepSeek 账号里发一条真实对话（留聊天记录）——测试前先说清楚
- 登录态会过期（跳到 `sign_in`）→ 需人工重新扫码，脚本层无法自解
- 上传大图前留意本机内存（~1.9G），别同时堆很多 Chrome 标签
