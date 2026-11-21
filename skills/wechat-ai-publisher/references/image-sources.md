# 图源清单与接入配方（Pexels 之外的免费源）

## 结论先行

| 源 | 可用性 | Key | 中国景点覆盖 | 授权与署名 |
|---|---|---|---|---|
| Pexels | 直连 1–2s，主源 | 已有（`douyin-card-pipeline/config.json` 的 `pexels_api_key`） | 一般 | Pexels License，免署名 |
| Wikimedia Commons | 可直接调 API，但**必须走代理** `127.0.0.1:9981` | 免 key | 强（县城级景点都有实拍） | CC0/PD 免署名；CC BY / CC BY-SA 需署名 |
| Pixabay | API 可达 | 需免费注册 | 弱 | Pixabay License，免署名 |
| Unsplash | API 可达 | 需免费注册（demo 50 次/小时） | 弱 | Unsplash License，免署名 |
| Openverse | 走代理会撞 Cloudflare 挑战页（403） | 免 key | 中 | CC，需按图署名 |

## Wikimedia Commons 接入配方

搜索（返回图片信息 + 授权 + 缩略图地址）：

```python
import json, urllib.request, urllib.parse
proxy = urllib.request.ProxyHandler({"http": "http://127.0.0.1:9981",
                                     "https": "http://127.0.0.1:9981"})
op = urllib.request.build_opener(proxy)
params = {
    "action": "query", "generator": "search",
    "gsrsearch": "Meili Snow Mountain filetype:bitmap",
    "gsrnamespace": "6", "gsrlimit": "50",
    "prop": "imageinfo", "iiprop": "url|size|extmetadata",
    "iiurlwidth": "2000", "format": "json",
}
u = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(params)
d = json.loads(op.open(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}),
                       timeout=40).read().decode())
for p in d["query"]["pages"].values():
    ii = p["imageinfo"][0]
    lic = ii.get("extmetadata", {}).get("LicenseShortName", {}).get("value", "")
    thumb = ii.get("thumburl")      # 2000px 宽，直接下载
    page = ii.get("descriptionurl")  # 备署名用
```

要点：

- **不加 `filetype:bitmap` 会混进 SVG/PDF**，绘图脚本处理会失败。
- **图片 CDN 也要走代理**：`upload.wikimedia.org` 直连超时，`thumb.wikimedia.org` 走代理 200。
- **429 会升级成长时间封锁**：搜索阶段词间 `sleep(0.3–1)` 够用；连续下载二十多张后，整个 IP 会被挡几十分钟，此时换 2200/1600/1280/1024 任意缩略尺寸都照样 429，`sleep 20–30` 也救不回来。正确做法：一次任务控制在该批次内下完，超了就把剩余候选记下来、隔一段时间再补；**不要靠换尺寸或狂重试绕限流**，会把封锁时间拖得更长。
- 完整整期图集用 Commons 时，把「下载 + 处理 + QC」跑成单次批处理（`scripts/commons_fetch.py`），别边搜边下边处理，减少请求密度。
- **授权过滤按 `LicenseShortName` 字符串**：`CC0` / `Public domain` / `PD` 免署名；`CC BY*`、`CC BY-SA*` 必须署名。
- 部分 CC0 图是从 Unsplash 迁入 Commons 的（标题带 `(Unsplash)`），画质通常比维基老照片好。
- **同一景点常被同一摄影师整组上传**：梅里 50 张里 22 张来自两个系列（`59066-…` 连拍、`Kawagebo 2009` 系列），先按 title 前缀或作者去重再计可用数；`Meili` 还会命中滑雪场压雪机品牌 Meili VM500，纯误命中。

## 素材量实测（决定要不要混源）

12 个中国景点关键词、约 500 条结果里：CC0/PD **只有 17 张**同时满足横图 + 宽 ≥1600，再过一遍现有画质闸门（锐度/灰暗）后剩 **7 张**。

放宽到宽 ≥1000 只多 2 张，而且都是废料（桂林 1024×768 老照片、纳木错 1278×722 卫星图），不值得为尺寸放宽标准。另一个实测：梅里雪山搜出来 50 张里 CC0/PD 为 0 张，黄山、张家界也是 0——CC0 覆盖率因题材而异，先用 API 数一下再决定，别假设“大景点一定多”。

结论：**只走 CC0/PD 撑不起 9–12 张的图集**。要么 CC0/PD 与 Pexels 混用（都不署名），要么放开到 CC BY 并在草稿末尾加一行来源署名。承接前先跟用户确认选哪种，别默认放宽授权。

> 用户对署名的态度是分场景的：日常图集默认**不署名**，优先 CC0/PD 与 Pexels；但明确到“某个只有 Commons 有实景的景点”（如岳阳楼）时，他可以接受 CC BY + 正文末尾一行署名。所以不要背成“他永远不接受署名”——先给两个方案和素材量，让他选；选完就按那种口径执行。

## 其他源实测

- **Burst（Shopify Stock Photos）**：页面 200、能解析 `burst.shopifycdn.com` 图链，但搜索不精准——`mountain` 结果里混信用卡、围裙、办公桌，不能当自动选题源。
- **Picjumbo**：页面 200，但图链不在常规 `uploads/*.jpg` 结构里，取不到图。
- **StockSnap / PxHere / Kaboompics / Pixabay 网页版 / Pexels 网页版**：直连 403（Cloudflare），别按网页 scrapping 方案设计。
- **不限制中国景点时**：Pexels 一个就够，全球风景覆盖好，不必再接新源；素材不足只发生在具体到某座中国山峰或县城景点时。

## 署名写法

- 全 CC0/PD：不需要任何署名，草稿里也不用加。
- 混入 CC BY / CC BY-SA：在正文末尾加一行纯文本，例如
  `图片来源：Wikimedia Commons，CC BY-SA 4.0`；逐张差异大时用图注标作者与许可。
- 复用某张图时保留 `descriptionurl`，被问起来能指回原始页面。
