# 随时间变化的数据源（实测清单）

2026-10-03 逐条实测。`✅` = 当场取到真实数据（附实测值）；`❌` = 当时不通。

## 专门收集「怪数据集」的站

用户问「有没有专门网站」时的答案。

| 站 | 说明 | 实测 |
|---|---|---|
| `data-is-plural.com` | 《Data Is Plural》全量存档：每周一期、2015 至今 500+ 期，几千个冷门数据集，可检索 | ✅ 200 |
| `tylervigen.com/spurious-correlations` | 2.5 万变量 × 6.36 亿次相关计算，专挑伪相关时序（凯奇电影数 vs 泳池溺亡） | ✅ 200 |
| `data-races.com` | 375 个现成排行数据集，还在实时追踪（GitHub stars / HuggingFace / Apple Music） | ✅ 200 |
| `datasetsearch.research.google.com` | 全网数据集搜索 | 未测 |
| `github.com/rfordatascience/tidytuesday` | 每周一个刁钻数据集，多为时序 | 未测 |

⚠️ `dataisplural.com`（**无连字符**）已经是域名停放页（114 字节跳转脚本），别用。

## 免 key 直接出时序的 API

| 源 | 端点 | 实测 |
|---|---|---|
| Wikimedia Pageviews | `wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia.org/all-access/user/<条目>/daily/<起>/<止>` | ✅ Nicolas_Cage 9/1 单日 9,076 |
| npm downloads | `api.npmjs.org/downloads/range/<起>:<止>/<包>` | ✅ react 2026-08-01 15,321,268 |
| PyPI stats | `pypistats.org/api/packages/<包>/recent` | ✅ requests 昨日 46,010,544 |
| Stack Exchange | `api.stackexchange.com/2.3/tags?site=stackoverflow` | ✅ c# 1,621,599 问 |
| Open-Meteo | 历史天气 archive 接口，任意经纬度逐日 | ✅ |
| OpenSky | 实时航班 | ✅ 抓到北京上空 CXA8211 |
| USGS | 全球实时地震 feed | ✅ |
| GitHub Archive | 2011 至今全部公开事件，按小时 gz | ✅ |
| Our World in Data | 直接下 grapher CSV | ✅ |
| World Bank | 各国指标 1960 至今（免 key） | ✅ |
| GBIF | 物种记录 | ✅ 39.5 亿条 |
| iNaturalist | 观测记录 | ✅ 3.9 亿条 |
| Wikimedia top-per-day | `wikimedia.org/metrics/pageviews/top/...` | ⚠️ 当时超时（per-article 正常） |

不通：CoinGecko（超时）、BoardGameGeek（403）、OpenAQ v2（已下线 410）、NYC Open Data（403）。

## 网络坑（重要）

本机**必须走全局代理** `127.0.0.1:9981`：`curl` 默认继承 proxy 秒回 200，加 `--noproxy '*'` 直连**超时**；`urllib` 即便走代理也容易 TLS 超时。
**结论：拉数据一律 `subprocess` + `curl`**（继承环境变量最省事）。

## 可做「怪选题」的方向

维基条目浏览量王座战（日粒度、常有反超名场面）· npm/PyPI 下载量之战（jQuery→React→Vue→Svelte）· Stack Overflow 标签兴衰（20 年跨度）· Steam 同时在线排行 · 全球地震次数按月 · 伪相关系列。

⚠️ 涉军/阅兵题材的**图片**素材不可靠（Pexels 张冠李戴），但**数据**（各国军费/兵力，SIPRI / World Bank）不受影响。
