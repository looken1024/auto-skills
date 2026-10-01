# 公众号草稿 API：文章类型决定 content 能力（含小程序链接）

沉淀自 2026-10-01：用户要求图集草稿正文写「高清原图看这里👉 这组图真的每一张都能当壁纸！」，**点击跳转小程序**。脚本原用 `newspic` + 正文拼 `#小程序://棱镜图库/Tz4ZusAKDlO6Yra`，用户实测「发布后根本不是链接，无法点击」。试了十余种写法全部无效，最后从官方文档定位到根因。

## 一、官方文档原文（决定性）

`POST /cgi-bin/draft/add` 的 `content` 字段说明：

> 图文消息的具体内容，支持 HTML 标签……**图片消息则仅支持纯文本和部分特殊功能标签如商品**，商品个数不可超过 50 个。

`article_type` 取值：`news`（图文消息，默认）、`newspic`（图片消息）。

| `article_type` | content 支持 | 能否做小程序链接 |
|---|---|---|
| `newspic` 图片消息 | **只有纯文本** + 少量特殊标签（如商品） | ❌ 不支持 |
| `news` 图文消息 | HTML | ✅ 支持 |

**结论：`newspic` 的 content 只存纯文本 → 任何小程序链接写法都不可能在图片消息里生效。遇到「链接点不动」先看类型，不要试写法。**

## 二、可用的三种链接样式（出自 `/cgi-bin/message/mass/uploadnewsmsg` 文档「注意事项」，适用于 `news` 的 content）

1. **文字跳转小程序**
   ```html
   <p><a data-miniprogram-appid="wx123123123" data-miniprogram-path="pages/index" href="">点击文字跳转小程序</a></p>
   ```
2. **小程序卡片跳转**
   ```html
   <mp-common-miniprogram data-miniprogram-appid="wx123123123" data-miniprogram-path="pages/index/index" data-miniprogram-title="小程序示例" data-miniprogram-imageurl="http://example.com/demo.jpg" data-miniprogram-type="card"></mp-common-miniprogram>
   ```
3. **图片跳转小程序**
   ```html
   <p><a data-miniprogram-appid="wx123123123" data-miniprogram-path="pages/index" href=""><img src="https://mmbiz.qpic.cn/mmbiz_jpg/demo/0?wx_fmt=jpg" alt=""></a></p>
   ```
4. 第三方编辑器等价变体（社区实践，属性更全）：
   ```html
   <a class="weapp_text_link" data-miniprogram-appid="wxe81de4a47ea1ab33" data-miniprogram-path="pages/index" data-miniprogram-nickname="小程序名称" data-miniprogram-type="text" data-miniprogram-servicetype="" href="">文字</a>
   ```

> `uploadnewsmsg` 文档另写「具备微信支付权限的公众号，可以使用 a 标签，其他公众号不能使用」；`draft/add` 文档没有这句限制。个人订阅号实测 `draft/add` **接受 `<a>` 且原样存储**（不是被过滤）。**但「能存进去」≠「发布后可点」——上线前必须实发一篇验证，别只看草稿。**

## 三、逐条验证矩阵（省得下次重试）

对 `newspic` 建草稿：

| 写法 | `draft/add` | 发布后可点 |
|---|---|---|
| `文字\n#小程序://名/短串` | ✅ 成功 | ❌ 用户实测不可点 |
| `文字#小程序://名/短串`（同行） | ✅ 成功 | ❌ |
| `文字\nweixin://mp.weixin.qq.com` | ✅ 成功 | — |
| `文字\nmp://名称` | ✅ 成功 | — |
| `文字\n[小程序]名称` | ✅ 成功 | — |
| `<a href="#小程序://名/短串">文字</a>`（HTML） | ❌ `45166 invalid content` | — |
| 链接塞进 `url` / `digest` / `source` 字段 | ✅ 成功（字段存下但不渲染） | ❌ |

要点：**`newspic` 传 HTML 会被 `45166 invalid content` 直接拒**（唯一会报错的写法，其余都「成功但无用」）→ **`draft/add` 返回 media_id 根本不能当验证通过**，必须 `draft/get` 回读或用 `draft/batchget` 看实际存储。

对 `news` 建草稿（实测）：
```python
content = ('<p>徽州古村的房子，墙比门高。</p>'
           '<p><a data-miniprogram-appid="wx489060715b335aaf" '
           'data-miniprogram-path="pages/index/index" href="">'
           '高清原图看这里👉 这组图真的每一张都能当壁纸！</a></p>')
# draft/add 传 article_type="news" + thumb_media_id（封面，永久素材）
# draft/get 回读 → content 与传入完全一致，<a> 标签与全部 data-* 属性原样保留
```
（状态：标签层已验证；**端到端「发布后真能点」当时尚未实发验证**——接手时先补这一步。）

## 四、换成 `news` 的代价（动之前先跟用户确认）

- `news` **必须有 `thumb_media_id`**（封面永久素材），否则 `no_cover`。
- 图片要按 HTML `<img>` 内嵌，src 必须是微信域内 url——用 `/cgi-bin/media/uploadimg` 拿 `mmbiz.qpic.cn` 链接；**外部图 url 会被过滤**。
- 不再是 `newspic` 的 `image_info.image_list`，**文章形态会明显改变**（图片消息 = 小绿书式多图轮播；图文消息 = 标题+正文+内嵌图）。
- 「小绿书式多图轮播」是 `newspic` 独有版式，切到 `news` 就没了。

## 五、怎么拿 `data-miniprogram-path`

- 公众号后台 → 编辑图文 → 顶部「小程序」→ 选中小程序 → 能看到**页面路径**（形如 `pages/index/index`）。
- API 侧拿不到：`wxamplinkget`（列关联小程序）报 `48001 api unauthorized`，个人主体号无「小程序管理」权限集。
- `#小程序://名称/xxxx` 里的 `xxxx` 是**分享短链标识**（小程序内「复制链接」生成），**不等于** `data-miniprogram-path`，别直接填。
- ⚠️ **别用「用户那篇链接能点」反推 `newspic` 支持链接**：用户是在后台编辑器里手动「插入小程序」，编辑器提供了 UI 能力；**API 对 `newspic` 不开放该能力**。两者不是一回事。

## 六、顺手记：草稿接口名与已发布列表

- **列表接口是 `draft/batchget`**（POST，body `{"offset","count","no_content"}`）。误写成 `draft/getdraft` 会返回 **`40066 invalid url`**——看着像 URL/编码问题，实为接口名不存在，别去查编码。
- **查单篇**：`draft/get` + `{"media_id"}`，能回读 `news_item[].content` 原文（核「写进去的 HTML 有没有被过滤」的唯一可靠手段）。
- **删草稿**：`draft/delete` + `{"media_id"}`，`errcode=0` 即成功。批量清理测试稿：`draft/batchget` 扫标题前缀 → 逐个删。**测试稿务必清掉**，会污染用户草稿箱（本次一次清掉 14 条）。
- **`freepublish/batchget` 可能报 `48001 api unauthorized`**（个人订阅号无该权限）→ **列不出已发布文章**。推论：文章群发后会从草稿箱消失、API 侧也查不到 → **归档/台账必须自己落盘**，别指望事后回查。
- 读取返回的中文别用 `r.json()`（会被当 Latin-1 解出假乱码），用 `json.loads(r.content.decode("utf-8"))`。
