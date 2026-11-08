# Pexels 图集流水线：话题池轮换 + 网络加速

适用：公众号图集（`wechat-ai-publisher/scripts/pexels_gallery_draft.py`）、抖音卡片、任何用 Pexels 按关键词抓图的 cron 流水线。

## 1. 系统代理是 Pexels 的最大性能陷阱（2026-11-03 实测）

本机全局 `http_proxy` / `https_proxy = http://127.0.0.1:9981`。同一请求对比：

| 目标 | 走系统代理 | 绕过代理直连 |
|---|---|---|
| `api.pexels.com/v1/search` | 32s（偶发 SSL handshake timeout） | **1.2s** |
| `images.pexels.com/...jpeg` | 40s 只下到 213KB 后超时 | **2.0s / 289KB** |

症状很像"Pexels 挂了/限流"：`URLError: _ssl.c:999 handshake operation timed out`、`SSL: UNEXPECTED_EOF_WHILE_READING`、下载 `IncompleteRead`，整条脚本卡死或产出不足。**先做直连对比，别先怀疑 API key 或额度。**

```bash
# 代理 vs 直连（注意 -x 与 env -u 的区别）
curl -s -o /dev/null -w "proxy %{http_code} %{time_total}s\n" -m 40 \
  -H "Authorization: $PEXELS_KEY" "https://api.pexels.com/v1/search?query=test&per_page=5"
env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY \
  curl -s -o /dev/null -w "direct %{http_code} %{time_total}s\n" -m 40 \
  -H "Authorization: $PEXELS_KEY" "https://api.pexels.com/v1/search?query=test&per_page=5"
```

### 代码修法（urllib，脚本内生效，不依赖 shell 环境）

```python
import urllib.request as _urlreq
_PEXELS_OPENER = _urlreq.build_opener(_urlreq.ProxyHandler({}))  # 显式忽略 env 代理

# 搜索 / 下载都用这个 opener
with _PEXELS_OPENER.open(req, timeout=30) as r:
    photos = json.loads(r.read()).get("photos", [])
```

同时给搜索和下载各加 **3 次重试**（间隔 2s）——Pexels 偶发 1 次失败，重试基本都能过：

```python
last = None
for attempt in range(3):
    try:
        ...
        return result
    except Exception as e:
        last = e
        if attempt < 2:
            time.sleep(2)
raise last
```

requests 写法：`requests.Session()` + `s.trust_env = False`（或 `s.proxies = {}`）。

> 只对 Pexels/图片 CDN 绕过；微信 API、GitHub 等仍按需走代理，别全局 `unset`。

## 2. 话题池结构（2026-11-03）

| 文件 | 用途 |
|---|---|
| `scripts/topics.json` | 通用池（约 150 条），每小时贴图任务用 |
| `scripts/topics_stunning.json` | "炫酷/不常见风景"专用池（71 条），每 2 小时图文任务用 |
| `scripts/topic_bank.json` | 候选银行 `{"pending":[],"used":[],"rejected":[]}` |

切换池子：脚本 `load_topics()` 读环境变量 **`GALLERY_TOPICS_FILE`**，没有则回退 `topics.json`。包装 shell 里：

```bash
export GALLERY_TOPICS_FILE="$SKILL_DIR/scripts/topics_stunning.json"
python3 scripts/pexels_gallery_draft.py --mode news
```

## 3. 轮换脚本 `rotate_topics.py`

每 3 天跑一次（cron `21a4b0cf5a35`，`every 72h`）。逻辑：

1. **判高频**：`窗口内被选次数 >= 2`（窗口默认 3 天）**或** `累计出图 >= 27 张`（与脚本内 `TOPIC_EXHAUSTED=30` 对齐，略提前）。
2. 按 `(窗口次数, 累计次数)` 降序，取前 `--remove-top`（默认 30）剔除。
3. **等量补充**：从 `topic_bank.json` 的 `pending` 取候选，跳过任何历史用过（按 ledger 里的 topic 名）或池中已有的 `cn`/`en`。
4. 每条候选调 Pexels 验证：`per_page=24&orientation=landscape`，横图 `>= 12` 才入池；失败进 `rejected`，成功进 `used`（永不重复）。
5. 池子大小保持不变；写入前备份 `topics.json` / `topic_bank.json`。
6. `--status` 只看银行余量；`--dry-run` 只算不写。

输出约定：人类可读摘要 + 最后一行 JSON（`removed`/`added`/`bank_pending`/`shortfall`）；`shortfall>0` 或 `bank_pending<60` 时，cron 的 agent 任务负责再生成 60 条候选补进银行。

### 已知坑

- **不要直接复用 `expand_topics.py` 的候选表**：它里面是早期被剔掉的老话题，一跑就把高频词原样加回来。轮换必须以 ledger 的"历史用过"集合做排除。
- **并发验证会把 Pexels 打崩**：10 并发时大量 `SSL: UNEXPECTED_EOF_WHILE_READING`；用 5-6 并发 + 对失败项顺序重试 3-4 次。
- `per_page=24` 返回 24 条只表示"至少 24"，不代表词很肥；足够 9 张图即可。
- 同日话题去重文件 `logs/gallery_topic_day.json` 是**多个图集任务共享**的，换池不会重置它——这是好事（防止两个任务同一天撞同一话题）。
- 换池/加词后务必跑一次 `--dry-run --count 3`，确认能选到新词、下载/压缩/画质闸门无报错。

## 4. 新增一批关键词的标准流程

1. 列出 `(中文名, 英文 Pexels 查询词)`，英文词带场景/光线限定（`desert starry sky`、`cliff beach sunrise`），避免搜出特写/证件照。
2. 用 Pexels API 批量验证，要求横图 ≥12（本机经验：通过率高的词通常返 23-24 张）。
3. 去重：排除当前池 + ledger 历史 topic 名。
4. 备份 `topics.json` 后写入，打印新增清单。
5. `grep` 检查 `cn`/`en` 无重复，再跑 dry-run。

## 5. 当前调度映射（2026-11-03）

| job | 调度 | 池子 | 产出 |
|---|---|---|---|
| `9d58e7843134` | `0 */2 * * *` | `topics_stunning.json` | `news` 图文（9 图 + 小程序链接） |
| `6b86d039a651` | `every 60m` | `topics.json` | `newspic` 纯贴图 |
| `21a4b0cf5a35` | `every 72h` | 轮换 + 银行 | 剔高频、补新词 |

> 两个图集任务并存时一天约 36 条草稿；加任务前先跟用户确认是否要停掉另一个，避免草稿箱被刷屏。

## 6. 图文标题：地点描述式（2026-11-03 用户要求）

**规则（只作用于 `--mode news`）**：
- 不再用「{话题}·每日图集（{日期}）」；标题要契合这个地点/景点，像一句有画面的短描述。
- 主题是**具体地名或景点**时，地名必须出现在标题里（地名后用「，」或「｜」与后半句隔开）；泛场景（银河拱桥、沙漠星空、海浪航拍）不要硬编地名。
- 12–24 字；禁「每日图集」「图集」；禁书名号/引号/日期/序号/浮夸营销词。
- `newspic` 贴图模式**保持旧格式**（用户只要求改图文任务）。

**实现**：`pexels_gallery_draft.py` 的 `make_title(topic)`：
1. 读 `OPENCODE_GO_API_KEY`（env 或 `~/.hermes/.env`），调 `deepseek-v4.1-flash`，`reasoning_effort=low` + `stream=False` + `max_tokens=3000`。
2. 请求头**必须带浏览器 UA + `Accept: application/json`**，否则 Cloudflare 返回 `403 error code: 1010`（默认 Python-urllib UA 被拦）。
3. 清洗：取第一行、去引号/书名号/前缀序号；校验 6–32 字且不含「图集」，不合格就用模板 `{topic}｜一眼心动的风景`。
4. 生成失败不阻断建稿，只打 stderr 并回退模板。

**验证**：跑一次真实 `news` 任务后，用 `draft/batchget` 拉草稿看 `news_item[0].title`（示例实测：「阿尔山天池，云影落入森林的眼」）。只改代码不跑真实路径验不出来——`--dry-run` 在建稿前就 return 了，不会触发 `make_title()`。

## 7. 单话题产量兜底：<5 张就删词换下一个（2026-11-07）

用户口径：某个关键词凑不出足够的有效图，就**把这个词从池子里永久删掉**，换下一个继续，别拿别的词的图凑数。

实现要点（`pexels_gallery_draft.py`）：

1. 常量 `MIN_VALID_IMAGES = 5`；下载循环的停止条件是 `len(picked) >= max(args.count, MIN_VALID_IMAGES)`——只写 `>= args.count` 的话，`--count 3` 永远凑不到 5，会误删好词。
2. 有效图不足时抛 `InsufficientImages(topic, count, skipped, rejected)`，由外层 `main()` 捕获。
3. 外层循环最多换 10 个词：
   - 自动选词模式：`remove_topic_from_pool(cn)` 原子写回当前 `GALLERY_TOPICS_FILE`，并同步内存里的 `TOPICS`；备份名 `.bak-removed-<ts>`。
   - `--dry-run`：只在内存里排除，不写文件（试跑不能改池子）。
   - 手动 `--topic`：只报「有效图片不足」并退出，不删词（一次性需求不该污染池子）。
4. **删掉旧的"兜底补图"逻辑**：原来 `photos < count*2` 时会拿 `TOPICS[0]`（雪山金顶）的图来凑，导致文章混入无关图、死词永远留在池里。现在不补，直接换词。

验证方法（可重复）：建一个只含死词的临时池，直接跑（非 dry-run）：
```bash
printf '[{"cn":"测试死词","en":"zzzzqqqqxxxxnoresult"}]' > /tmp/test_pool.json
GALLERY_TOPICS_FILE=/tmp/test_pool.json python3 scripts/pexels_gallery_draft.py --count 3 --mode news
cat /tmp/test_pool.json                      # 应为 []
ls /tmp/test_pool.json.bak-removed-*         # 应有备份
```
注意 Pexels 对乱码查询也会模糊返回几条图，所以"死词"不一定真的 0 结果；验证的是**不足 5 张时的删词与换词路径**，不是搜索为空。

## 8. 多路查询与"一篇只写一个国家"（2026-11-08）

新增参数：

| 参数 | 作用 |
|---|---|
| `--queries "q1\|q2\|q3"` | 多路 Pexels 查询，按**轮询**把各自结果交错合并，适合多城市/多国家拼一篇 |
| `--country 肯尼亚` | 标题里**必须**出现该国名；模型没写就判不合格，最终回退 `国家｜主题` |
| `--title-context "..."` | 给标题生成的补充信息（人物、场景、国家） |

用户口径（2026-11-08）：**一篇文章只用一个国家**，国家名写进标题。做「贫民窟/底层生活」这类题材时：

```bash
# 单国家 + 人物导向查询（全部肯尼亚）
GALLERY_TOPICS_FILE=/tmp/slum_pool.json python3 scripts/pexels_gallery_draft.py \
  --mode news --topic 贫民窟 --count 9 --country 肯尼亚 \
  --queries "kibera slum people|nairobi kibera life|kenya slum child" \
  --title-context "肯尼亚内罗毕基贝拉的贫民窟日常，画面里有人物"
# 产出标题示例：肯尼亚基贝拉，贫民窟日常里的人间剪影
```

要点：
- 人物/底层题材的查询必须带 `people` / `daily life` / `child` / `family`，只搜地名会全是空景航拍。
- 多国素材不要混进同一篇；一个国家跑一次，标题带国名。
- 想避开"脏乱差"观感时用 `favela colorful houses` 这类词（彩色山坡贫民窟），比 `slum poverty` 的垃圾/污水纪实图更适合公众号。
- 一次性专题用临时池文件（`/tmp/xxx_pool.json`），不要写进常规轮换池。

## 9. 批次增删关键词：实操口径（2026-11）

用户会按类别下指令（"峡谷的去掉"、"动物都去掉"、"冰川去掉"、"加雕塑和海滩"）。做法：

1. **先列命中项再删**，把中文名和英文查询词一起打出来，让用户能核对边界（例如"峡湾算不算峡谷"）。
2. **两个池 + 银行都要清**：`topics.json`、`topics_stunning.json`、`topic_bank.json` 的 `pending`（`used` 是历史记录可不动）。只清一个池，另一个池还会继续出。
3. 匹配规则要写清楚：`"峡谷" in cn` / `cn.endswith("峡")` / `canyon|gorge`；**峡湾 fjord 要排除**（用户认为峡湾不算峡谷，且是水景+峭壁，保留）。动物类按名单精确匹配，别用 `"羊"`、`"象"` 这种子串（会误伤羊卓雍措、抽象油画、牯牛降、老牛湾）。
4. **加词前必须验 Pexels**：`per_page=24&orientation=landscape`，横图 ≥12 才收；5-6 并发、失败项顺序重试 3 次（10 并发会大量 SSL EOF）。
5. 写回前 `shutil.copy2` 备份；写完用 Python 检查 `cn`/`en` 无重复；再跑一次 `--dry-run --count 9` 抽一个新词验证全链路。

截至 2026-11-08 的池子规模：`topics.json` 160 条、`topics_stunning.json` 99 条、`topic_bank.pending` 52 条（数字会随轮换变，别当常量）。

**Pexels 的"世界名画"陷阱**：搜 `famous oil painting` / `renaissance painting` 返回的大多是**博物馆实拍、天顶壁画、画廊墙面、画家调色盘**，不是《星月夜》《蒙娜丽莎》这类真迹高清。做"名画"专题要真迹就去维基共享资源/大都会 Open Access，Pexels 只能做"艺术氛围"。
