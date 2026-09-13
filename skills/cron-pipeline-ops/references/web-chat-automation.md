# 用 browser_exec 驱动网页版大模型（登录 / 发送 / 抓回复）

以 `chat.deepseek.com` 为例（2026-09-13 实测跑通：登录 + 发 2.8k 字提示 + 抓到 3.7k 字回复）。同类 SPA 聊天站大体同理。

## 1. 登录

1. `goto_url("https://chat.deepseek.com")` → 自动跳 `/sign_in`（直连即可）。
2. 手机号登录：第一个 `input[type=tel]` 填手机号 → 点「发送验证码」。
3. **点「发送验证码」前会弹图形验证码**（数美 spatial_select，图来自 `castatic.fengkongcloud.cn`，题面形如「点击图中最小的蓝色圆柱体」）：
   - 取验证码 `img` 的 `src` → `curl --noproxy '*'` 下载原图（常 600×300）；
   - PIL 找目标颜色像素质心得图内坐标 `(ix, iy)`（例：蓝 = `b > r+25 and b > g+25 and b > 90`）；
   - 取该 `img` 的 `getBoundingClientRect()`，映射 `px = rect.x + ix/naturalWidth*rect.width`、`py = rect.y + iy/naturalHeight*rect.height` → `click_at_xy(px, py)`；
   - 点对后弹窗关闭、页面提示「验证码已发送至 …」、按钮变「60 秒后可再次获取」。
4. **短信可能延迟 1-2 分钟**；期间可能弹“当前网络不佳，请刷新重试”（风控脚本加载抖动，别急着重发）。用户给码后填入第二个 `input`，点「登录」，URL 跳到聊天页即成功。
5. 登录态落在所用浏览器 profile 里；多个平台可能共用同一个无头实例（cookie 按域隔离）。

## 2. 发消息

1. 新对话：`goto_url("https://chat.deepseek.com/")`。
2. 可选：点「深度思考」开推理模式（分析质量更好）；「智能搜索」会联网引用信源。
3. 输入框是 **`textarea`（不是 contenteditable）**：`document.querySelector('textarea').focus()`，再用 CDP `Input.insertText` **分块插入**（每块 ~800 字、块间 sleep 0.5s；长文一次性插入易被截断），插完回读 `textarea.value.length` 校验。
4. 发送：`Input.dispatchKeyEvent` 发 Enter（keyDown+keyUp，`key='Enter'`, `code='Enter'`, `windowsVirtualKeyCode=13`）。发送后 textarea 清零即已发出。

## 3. 抓回复（关键坑）

- ⚠️ **`document.body.innerText` 抓不到正文**（常只有几十字，如“新对话 深度思考 智能搜索 内容由 AI 生成”）——聊天区是虚拟化渲染。
- 正确姿势：取所有 `[class*="markdown"],[class*="Markdown"]` 容器的 `innerText`，过滤长度 >50，**取最长的那条**就是回复正文（实测 3719 字）。
- 等待：每 12s 轮询页面文本长度，连续几次不变即完成（开深度思考+联网通常 1-3 分钟）；`capture_screenshot()` 可看进度并留证。
- 留证：回复存文件（如 `logs/ds_review_YYYY-MM-DD.md`），向用户汇报要点而非整篇粘贴。

## 4. 注意

- 机房 IP 用网页版容易触风控；**批量任务走 API 更稳**（若本机已配对应 provider/key），网页版适合偶尔做一次人工级复盘。
- 抓“当天已发内容”用于复盘：打开平台后台列表页，取条目容器（如 `.post-item`）的 `innerText`，按时间戳切分并存 JSON。
- 复盘 prompt 模板（微头条场景）：逐条点评（钩子/观点/事实风险）→ 共有套路与盲点 → 事实错误与合规风险 → 3 条可落地改进 → 只保留一条留哪条；并要求“直接给分析、不要客套”。

## 5. 脚本化终审（裸 CDP，不依赖 browser_exec / harness）

实测：把「发布前把稿子丢给网页版模型终审」做成**流水线固定步骤**时，用裸 CDP 直连浏览器调试端口更稳——`http://127.0.0.1:9222/json` 取页面列表 → `websocket` 连目标页 → `Page.navigate` / `Runtime.evaluate`，不用 browser-harness 的 `js()`（多标签场景会读到别的上下文）。落地脚本：`~/.hermes/skills/toutiao-micro-publish/scripts/ds_web_review.py`。

要点：
1. **独享标签页**：别复用头条/公众号后台正在用的标签，为终审新开一个 `chat.deepseek.com` 标签，用完关掉。
2. **无头后台标签会被节流**（页面不渲染、文本不变、await 超时）：`Emulation.setFocusEmulationEnabled {enabled:true}` + `Page.bringToFront`，并周期性 `Page.captureScreenshot`（哪怕不存图）强制重绘，否则永远只拿到 loading 骨架。
3. **`Network.setUserAgentOverride` 带 `suppress_origin: true`**，否则部分站点因 Origin 头不匹配拒绝渲染。
4. **输入**：`textarea.focus()` → CDP `Input.insertText` 分块（~800 字/块）→ 回读 `value.length` 校验 → `Input.dispatchKeyEvent` 发 Enter（同本文件第 2 节）。
5. **解析**：等页面出现判定标记后再取容器（第 3 节的 `[class*="markdown"]` 取最长法）；**prompt 里要求模型最后单独一行输出机器可读判定**（`VERDICT: PASS` / `VERDICT: FIX` + 必改项），脚本只认这一行，别解析自然语言。⚠️ 选容器时必须排除「包含本次 prompt 特征串」的那个——否则会把自己发的提问读成回复（实测因正则转义在 Python 拼 JS 时被吃掉而误判）。
   **多套 prompt 模板（多 `--mode`）时的追加坑（2026-09-13 实测）**：排除清单必须是**所有模板**的特征串，不能只写当前默认模板的。公众号模板用的是 `【待审文章】`，脚本只排除了微头条模板的 `【待发内容】` → 「输出格式」里那句 `VERDICT: PASS` 恰好命中最小的那个容器 = 把提问当回答抓回来（返回长度正好等于 prompt 长度）。修法：把这些一起排掉——`【待发内容】/【待审文章】/【复核清单】/按此写/不要复述我的要求`；再加**防呆断言**：抓到的文本里若含任一提问标记，直接 `raise`（宁可报错也不要静默交付一份“看起来成功”的假回答）。
   换 mode 的落地做法：`--mode weitoutiao|gzh` 两套模板（微头条=短稿事实/合规/结尾查重；公众号=日期/数字/机构/条款号/引号原文/绝对化/AI味/平台适配 8 项），查重素材按 mode 自动取（微头条取台账最近 5 条、公众号取本号归档最近 10 篇标题）。
6. **耗时与失败策略**：单次 5-8 分钟（开深度思考更久）。抓不到判定/超时的口径要**写进 prompt**：本次采用 fail-closed（停发 + 邮件告警，不自动发布）。
7. **留证**：每次终审把 prompt+回复落盘（如 `logs/ds_review_YYYY-MM-DD.md`），便于事后追。
8. **登录态是硬依赖**：过期会跳 `/sign_in`，这时必须停发并告警，不能"当通过"继续发。

