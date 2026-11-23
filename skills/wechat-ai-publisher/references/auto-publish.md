# 自动发布：能力边界与扫码登录路径

## 结论

- **草稿 API 有权限，群发/发表 API 没有。** 本号（未认证订阅号）对 `freepublish/*` 和 `message/mass/*` 全部返回 `48001 api unauthorized`；`draft/*`、素材、`uploadimg` 正常。
- 因此“产出即群发、全无人值守”做不到。可行的最接近方案是 **后台网页的「定时发表」**：内容进去后设好时间，到点由微信自己发；仍需登录态，登录态会过期。
- 另一条是升级为认证服务号（才有群发接口），个人订阅号基本无解。

## 只读探测（先确权，别拿发布接口试）

```python
# 均只读，不会发出任何内容
POST /cgi-bin/freepublish/batchget  {"offset":0,"count":1,"no_content":1}
POST /cgi-bin/message/mass/get      {"msg_id":"0"}
POST /cgi-bin/draft/count           {}
```

返回 `48001` 即无权限。**绝不要用 `freepublish/submit` 去“试一下”**——一旦这个号真有权限，那就是立刻群发给全部粉丝，没有撤销。

## 扫码登录（不依赖浏览器，实测可用）

浏览器跑不起来时，这条 HTTP 路径照样能拿到可扫的二维码。

1. 取 uuid（表单 POST，带 `Referer: https://mp.weixin.qq.com/`）：

```
POST https://mp.weixin.qq.com/cgi-bin/bizlogin?action=startlogin
Content-Type: application/x-www-form-urlencoded
body: userlang=zh_CN&redirect_url=&login_type=3&sessionid=&token=&lang=zh_CN&f=json&ajax=1

→ {"base_resp":{"ret":0,"err_msg":"ok"},"uuid":"<uuid>"}
   响应头带 Set-Cookie: uuid=<uuid>
```

2. 取二维码图：

```
GET https://mp.weixin.qq.com/cgi-bin/scanloginqrcode?action=getqrcode&uuid=<uuid>
Cookie: uuid=<uuid>
Referer: https://mp.weixin.qq.com/

→ 200 image/jpg，472×472 灰度 JPEG
```

3. **拿到就立刻发给用户**（`MEDIA:/path/qr.jpg`），二维码几分钟就过期，不要在中间插别的活。用户明确要求“需要扫码的时候发二维码给我”。

4. 登录完成的判定：**不要只信 `action=ask` 的 status**。实测用户已扫码后 `ask` 仍长时间返回 `status:1`，真正完成是调用：

```
POST https://mp.weixin.qq.com/cgi-bin/bizlogin?action=login&uuid=<uuid>
body: userlang=zh_CN&redirect_url=&login_type=3&sessionid=&token=&lang=zh_CN&f=json&ajax=1

→ {"base_resp":{"ret":0},"redirect_url":"/cgi-bin/home?t=home/index&lang=zh_CN&token=<token>"}
   响应 Set-Cookie 带 bizuin / data_bizuin / slave_bizuin / data_ticket / slave_sid / ua_id
```

把 cookie 存成 curl cookie jar（`-c`），后续请求用 `-b` 带它。

5. 验证会话是否真的有效：

```
GET /cgi-bin/home?t=home/index&lang=zh_CN&token=<token>
→ 200，约 290KB，页面里有 nick_name
```

## 后台网页接口的边界（实测）

- 登录后后台编辑器页面能 200 打开（`/cgi-bin/appmsg?t=media/appmsg_edit_v2&action=edit&isNew=1&type=77&token=...`，type=77 是贴图）。
- 但页面里引用的 `appmsg_edit_v2_gray_fe.*.js` 只暴露 `operate_appmsg?sub=check_sourceurl / collaboration_* / decode_qrcode / delete_auto_save_appmsg / save_mp_comment_option` 这类辅助接口；**新建/保存/发表贴图的那套参数不在可读的 JS 里**。
- 结论：到此为止是“登录可用、后台可读”，**发表仍走不了**。不要靠猜字段去 POST `operate_appmsg` / `masssendmodify`：参数错会造垃圾草稿，猜对了就是直接群发，两条都不该试。
- 浏览器不可用时，正确收尾是：把登录态存好（cookie jar + token），告诉用户“登录成功、草稿可自动建，发表要手动点两下或换一台能跑浏览器的机器”，不要把一个未验证的私有接口包装成“自动发布”。

## 定时发表（浏览器可用时）

后台“贴图/图文消息”编辑器 → 填标题正文 → 发表 → 打开「定时发表」选时间 → 发表。到点微信执行，不需要本机在线。扫码确认这一步挡不住，别设计成无人流程。

## 对用户的话术

- 先说清“API 没有群发权限”，再给“扫码 + 定时发表”的方案，不要含糊其词。
- 不要承诺“以后不用管了”；如实说：登录态一般撑几天，掉了要重扫。
- 发布类操作永远停在扫码/确认前，等用户点头。
