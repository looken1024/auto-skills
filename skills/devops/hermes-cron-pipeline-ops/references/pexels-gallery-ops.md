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
