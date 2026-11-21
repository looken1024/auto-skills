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
- **429 会间歇出现**：连续搜 10+ 个词就会触发，词间 `sleep(0.3–1)`，命中 429 就退避重试，别当成源挂了。
- **授权过滤按 `LicenseShortName` 字符串**：`CC0` / `Public domain` / `PD` 免署名；`CC BY*`、`CC BY-SA*` 必须署名。
- 部分 CC0 图是从 Unsplash 迁入 Commons 的（标题带 `(Unsplash)`），画质通常比维基老照片好。

## 素材量实测（决定要不要混源）

12 个中国景点关键词、约 500 条结果里：CC0/PD **只有 17 张**同时满足横图 + 宽 ≥1600，再过一遍现有画质闸门（锐度/灰暗）后剩 **7 张**。

放宽到宽 ≥1000 只多 2 张，而且都是废料（桂林 1024×768 老照片、纳木错 1278×722 卫星图），不值得为尺寸放宽标准。另一个实测：梅里雪山搜出来 50 张里 CC0/PD 为 0 张，黄山、张家界也是 0——CC0 覆盖率因题材而异，先用 API 数一下再决定，别假设“大景点一定多”。

结论：**只走 CC0/PD 撑不起 9–12 张的图集**。要么 CC0/PD 与 Pexels 混用（都不署名），要么放开到 CC BY 并在草稿末尾加一行来源署名。承接前先跟用户确认选哪种，别默认放宽授权。

## 署名写法

- 全 CC0/PD：不需要任何署名，草稿里也不用加。
- 混入 CC BY / CC BY-SA：在正文末尾加一行纯文本，例如
  `图片来源：Wikimedia Commons，CC BY-SA 4.0`；逐张差异大时用图注标作者与许可。
- 复用某张图时保留 `descriptionurl`，被问起来能指回原始页面。
