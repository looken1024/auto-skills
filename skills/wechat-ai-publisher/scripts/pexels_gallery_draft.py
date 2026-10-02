#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每小时公众号图集草稿：Pexels 抓 9 张横图 → 左右翻转+滤镜(不叠字) → 传微信素材 → 建草稿箱贴图(newspic)

用法:
  python3 pexels_gallery_draft.py [--topic 秋天] [--count 9] [--dry-run]

md5 去重（2026-08-29 用户要求）:
  - 下载原图后立即计算 md5，查台账 logs/gallery_sent_md5.json，发过的图片直接剔除不重复发
  - 仅在草稿创建成功后才把本次 md5 写入台账（失败不记录，可重试）
  - 台账结构: {"md5s": {"<md5>": {"pexels_id":..,"topic":..,"ts":..}}, "list": [...]}

依赖: Pillow + requests + numpy（wechat-ai-publisher 环境已有）
配置: Pexels key 从 douyin-card-pipeline/config.json 读; 微信 .env 从本 skill 目录读
"""
import os, sys, json, random, shutil, argparse, tempfile, hashlib, glob, time
import requests
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
import config as wc_config
import compress_image

# ---------- 话题池：中文名 → Pexels 英文搜索词 ----------
# 话题池独立存于 scripts/topics.json（每3天由 expand_topics.py 补充），脚本优先读它；
# 若文件缺失则回退到下方内置列表。
TOPICS_JSON = os.path.join(SCRIPT_DIR, "topics.json")

def load_topics():
    if os.path.exists(TOPICS_JSON):
        try:
            data = json.load(open(TOPICS_JSON, encoding="utf-8"))
            pairs = []
            for d in data:
                if isinstance(d, dict):
                    cn, en = d.get("cn"), d.get("en")
                elif isinstance(d, (list, tuple)) and len(d) >= 2:
                    cn, en = d[0], d[1]
                else:
                    continue
                if cn and en:
                    pairs.append((cn, en))
            if pairs:
                return pairs
        except Exception as e:
            print(f"! 读取 topics.json 失败({e})，回退内置列表", file=sys.stderr)
    return _BUILTIN_TOPICS


_BUILTIN_TOPICS = [
    # --- 自然景观 ---
    ("雪山金顶", "snow mountain golden sunrise"),
    ("冰川湖", "glacial lake turquoise"),
    ("薰衣草花田", "lavender field rows"),
    ("油菜花田", "rapeseed flower field"),
    ("红树林", "mangrove forest roots water"),
    ("萤火虫森林", "fireflies night forest"),
    ("樱花小径", "cherry blossom path"),
    ("桃花林", "peach blossom orchard"),
    ("胡杨林", "poplar forest desert autumn"),
    ("白桦林", "white birch trees forest"),
    ("高山野花", "wildflower alpine meadow"),
    ("湿地芦苇", "reed marsh sunset"),
    ("热带海岛航拍", "tropical island aerial"),
    ("滩涂倒影", "tidal flat reflection"),
    ("蓝冰洞", "glacier ice cave"),
    ("雪原日出", "snowfield sunrise cold"),
    ("高原湖泊", "plateau lake mountains"),
    ("温泉雾气", "hot spring steam winter"),
    ("峡谷晨曦", "canyon sunrise mist"),
    ("沙漠绿洲", "desert oasis palm trees"),
    ("瀑布彩虹", "waterfall rainbow mist"),
    ("云瀑", "cloud waterfall mountain ridge"),
    ("银河星空", "milky way night sky"),
    ("极光湖面", "aurora lake reflection"),
    ("秋日葡萄园", "vineyard autumn rows"),
    ("茶山", "tea plantation hills"),
    ("松林晨雾", "pine forest morning fog"),
    ("海边礁石", "rocky coast waves crash"),
    ("珊瑚礁", "coral reef underwater fish"),
    ("芦苇荡夕阳", "reed field golden sunset"),
    # --- 建筑 ---
    ("骑楼老街", "arcade shophouse street"),
    ("碉楼", "watchtower fortress village"),
    ("四合院", "chinese courtyard house"),
    ("红砖厝", "minnan red brick house"),
    ("江南园林", "chinese classical garden"),
    ("木构寺庙", "wooden temple hall"),
    ("石拱桥", "ancient stone arch bridge"),
    ("廊桥", "covered wooden bridge"),
    ("老钟楼", "clock tower old town"),
    ("旋转楼梯", "spiral staircase architecture"),
    ("拱廊", "colonnade arches corridor"),
    ("红砖厂房", "red brick industrial building"),
    ("玻璃穹顶", "glass dome ceiling"),
    ("清水混凝土教堂", "brutalist concrete church"),
    ("阶梯住宅", "terraced hillside houses"),
    ("水上木屋", "stilt house over water"),
    ("白墙黑瓦", "white wall black tile house"),
    ("尖顶山村", "alpine chalet village"),
    ("山城阶梯", "hillside steps city"),
    ("老城门", "ancient city gate wall"),
    ("伊斯兰穹顶", "islamic dome mosque architecture"),
    ("彩色房子", "colorful houses street"),
    ("石板小巷", "cobblestone alley old town"),
    ("铁艺阳台", "wrought iron balcony facade"),
    ("礁石灯塔", "lighthouse rocky coast"),
    # --- 世界地标 / 古迹 ---
    ("新天鹅堡", "neuschwanstein castle"),
    ("圣瓦西里大教堂", "saint basil cathedral moscow"),
    ("查理大桥", "charles bridge prague"),
    ("佛罗伦萨大教堂", "florence duomo"),
    ("圣彼得大教堂", "st peters basilica vatican"),
    ("威斯敏斯特教堂", "westminster abbey london"),
    ("巴黎圣母院", "notre dame cathedral paris"),
    ("许愿池", "trevi fountain rome"),
    ("奥林匹亚遗址", "olympia greece ruins"),
    ("卡兹尼神殿", "petra treasury jordan"),
    ("卢克索神庙", "luxor temple egypt"),
    ("阿布辛贝神庙", "abu simbel temple"),
    ("卡纳克神庙", "karnak temple columns"),
    ("泰姬陵花园", "taj mahal garden"),
    ("巴戎寺", "bayon temple faces"),
    ("蒲甘佛塔", "bagan temples myanmar"),
    ("婆罗浮屠", "borobudur temple"),
    ("富士山湖景", "mount fuji lake reflection"),
    ("清水寺", "kiyomizu temple kyoto"),
    ("伏见稻荷", "fushimi inari torii gates"),
    ("严岛神社", "itsukushima shrine torii"),
    ("东大寺", "todaiji temple nara"),
    ("景福宫", "gyeongbokgung palace seoul"),
    ("大皇宫", "grand palace bangkok"),
    ("纽约中央公园", "central park new york autumn"),
    ("金门大桥", "golden gate bridge fog"),
    ("布鲁克林大桥", "brooklyn bridge new york"),
    ("云门", "cloud gate chicago"),
    ("蓝顶教堂", "santorini blue dome"),
    ("五渔村", "cinque terre italy village"),
    ("哈尔施塔特", "hallstatt austria lake"),
    ("布莱德湖", "lake bled slovenia"),
    ("罗滕堡", "rothenburg germany old town"),
    ("科尔马", "colmar france canal houses"),
    ("古埃尔公园", "park guell barcelona"),
    ("里斯本电车", "lisbon tram yellow"),
    ("伊斯坦布尔天际线", "istanbul mosque skyline"),
    ("红场", "red square moscow"),
    ("马特洪峰", "matterhorn switzerland"),
    ("多洛米蒂", "dolomites italy mountains"),
    # --- 人文生活 ---
    ("早市摊位", "morning market stalls vegetables"),
    ("花店门口", "flower shop storefront"),
    ("面包店", "bakery shop interior"),
    ("老理发店", "old barbershop interior"),
    ("唱片店", "vinyl record store"),
    ("旧书摊", "secondhand book stall street"),
    ("街头画家", "street artist painting easel"),
    ("街头下棋", "elderly playing chess street"),
    ("早茶点心", "dim sum tea house"),
    ("面馆烟火", "noodle shop steam kitchen"),
    ("烧烤摊", "street bbq grill night"),
    ("糖画手艺人", "sugar painting artisan"),
    ("竹编工匠", "bamboo weaving craftsman"),
    ("染布坊", "indigo dye fabric workshop"),
    ("皮影戏", "shadow puppet performance"),
    ("木偶戏", "puppet show stage"),
    ("龙舟训练", "dragon boat rowing team"),
    ("赶海", "tidal flat shellfish gathering"),
    ("采茶人", "tea picking hands basket"),
    ("渔港归来", "fishing boat returning harbor"),
    ("修表匠", "watch repair craftsman"),
    ("缝纫老店", "tailor shop sewing machine"),
    ("修鞋摊", "shoe repair street stall"),
    ("老照相馆", "old photo studio interior"),
    ("旧邮局窗", "vintage post office window"),
    ("火车窗景", "view from train window"),
    ("骑行小路", "cycling path countryside"),
    ("露台夜谈", "rooftop evening gathering"),
    ("冬日窗边", "winter window reading cozy"),
    # --- 夜市 ---
    ("灯笼夜市", "lantern night market"),
    ("台湾夜市", "taiwan night market stalls"),
    ("曼谷夜市", "bangkok night market street"),
    ("海鲜夜市", "seafood night market"),
    ("夜市烧烤摊", "bbq night market grills"),
    ("糖葫芦摊", "candied fruit street stall"),
    ("灯会", "chinese lantern festival night"),
    ("庙会", "temple fair crowd"),
    ("圣诞市集", "christmas market stalls night"),
    ("灯光装置", "light installation street art"),
    ("霓虹招牌", "neon signs street night"),
    ("夜宵摊", "late night food stall"),
    ("夜市游戏摊", "carnival game booth night"),
    ("河灯", "floating lantern river night"),
]

TOPICS = load_topics()

PEXELS_CFG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..",
                          "douyin-card-pipeline", "config.json")
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs")
LEDGER_FILE = os.path.join(LOG_DIR, "gallery_sent_md5.json")
TOPIC_DAY_FILE = os.path.join(LOG_DIR, "gallery_topic_day.json")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"}


# ---------- 话题级去重（同一天不重复选话题） ----------
TOPIC_EXHAUSTED = 30   # 单话题累计已发超过此数视为检索池吃穿，选题时排除（2026-09-14）

def load_topic_usage(ledger):
    """从 md5 台账统计每个话题已发图片数: {"秋天": 79, ...}"""
    from collections import Counter
    return Counter(v.get("topic") for v in ledger.get("md5s", {}).values())

def load_topic_day():
    """读取当天已用话题记录: {"2026-08-29": {"topics": ["秋天", ...]}} """
    if os.path.exists(TOPIC_DAY_FILE):
        try:
            data = json.load(open(TOPIC_DAY_FILE, encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return {}


def record_topic_day(topic):
    """草稿创建成功后记录当天已用话题。"""
    today = datetime.now().strftime("%Y-%m-%d")
    data = load_topic_day()
    day = data.setdefault(today, {"topics": []})
    if topic not in day["topics"]:
        day["topics"].append(topic)
    tmp = TOPIC_DAY_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, TOPIC_DAY_FILE)


# ---------- md5 台账 ----------
def load_ledger():
    """读取已发送图片 md5 台账。返回 {"md5s": {md5: info}, "list": [md5,...]}"""
    if os.path.exists(LEDGER_FILE):
        try:
            data = json.load(open(LEDGER_FILE, encoding="utf-8"))
            if "md5s" not in data:
                # 兼容旧格式 list
                md5s = {m: {"ts": "unknown"} for m in data.get("list", [])}
                data = {"md5s": md5s, "list": list(md5s.keys())}
            return data
        except Exception:
            pass
    return {"md5s": {}, "list": []}


def save_ledger(ledger):
    os.makedirs(LOG_DIR, exist_ok=True)
    tmp = LEDGER_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(ledger, f, ensure_ascii=False, indent=1)
    os.replace(tmp, LEDGER_FILE)


def record_sent(entries):
    """草稿创建成功后记录本次图片 md5。entries: [{md5, pexels_id, topic}]"""
    ledger = load_ledger()
    ts = datetime.now().isoformat()
    for e in entries:
        m = e["md5"]
        if m not in ledger["md5s"]:
            ledger["md5s"][m] = {
                "pexels_id": e.get("pexels_id"),
                "topic": e.get("topic"),
                "ts": ts,
            }
            ledger["list"].append(m)
    save_ledger(ledger)


def md5_file(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------- Pexels ----------
def get_pexels_key():
    if os.path.exists(PEXELS_CFG):
        data = json.load(open(PEXELS_CFG))
        key = data.get("pexels_api_key", "")
        if key:
            return key
    raise Exception("Pexels API key 未配置 (douyin-card-pipeline/config.json)")


def pexels_search(query, per_page=40, orientation="landscape"):
    import urllib.request, urllib.parse
    key = get_pexels_key()
    url = "https://api.pexels.com/v1/search?query=%s&per_page=%d&orientation=%s" % (
        urllib.parse.quote(query), per_page, orientation)
    req = urllib.request.Request(url, headers={"Authorization": key, **UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read()).get("photos", [])


def pexels_fetch(photo_id, out, original_url=None):
    """下载原图。优先用 API 返回的 src.original（全分辨率），否则退回压缩 URL。"""
    import urllib.request
    if original_url:
        url = original_url
    else:
        url = ("https://images.pexels.com/photos/%d/pexels-photo-%d.jpeg"
               "?auto=compress&cs=tinysrgb&w=1920&h=1080&fit=crop" % (photo_id, photo_id))
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
    with open(out, "wb") as f:
        f.write(data)
    return out


def process_image(src, dst):
    """左右翻转 + 滤镜（对比度/色彩/亮度微调）+ 轻噪点，不叠字。

    内存（2026-10-01 修复 OOM）：本机只有 ~2G 内存，原来 `np.random.normal(...)`
    会对整图生成 float64 噪声数组（2500×3750×3 → 225MB，加上加法/clip 的临时数组
    峰值 500MB+），9 张连跑必被 OOM Killer 干掉。改为 **float32 + 分行块** 加噪，
    峰值降到 ~150MB/张。超大图仍先缩到短边 ≤2500。
    """
    from PIL import Image, ImageEnhance
    import numpy as np
    im = Image.open(src).convert("RGB")
    w, h = im.size
    # 长边也设上限：竖图 2500×3750 的数组仍然很大
    if max(w, h) > 3000:
        ratio = 3000 / max(w, h)
        im = im.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
    if min(w, h) > 2500:
        ratio = 2500 / min(w, h)
        im = im.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
    im = im.transpose(Image.FLIP_LEFT_RIGHT)
    im = ImageEnhance.Contrast(im).enhance(random.uniform(1.05, 1.12))
    im = ImageEnhance.Color(im).enhance(random.uniform(0.95, 1.08))
    im = ImageEnhance.Brightness(im).enhance(random.uniform(0.98, 1.05))
    # 轻噪点（标准差 2-3.5）打散指纹：float32 + 逐行块，避免整图大数组
    sigma = random.uniform(2.0, 3.5)
    arr = np.asarray(im).astype(np.float32)
    band = 256
    for y in range(0, arr.shape[0], band):
        blk = arr[y:y + band]
        blk += np.random.normal(0.0, sigma, blk.shape).astype(np.float32)
        np.clip(blk, 0, 255, out=blk)
    out = Image.fromarray(arr.astype(np.uint8))
    del arr
    out.save(dst, "JPEG", quality=88)
    return dst


# ---------- 微信 ----------
def _get_token(app_id, app_secret):
    from retry_util import request_with_retry
    r = request_with_retry('GET', "https://api.weixin.qq.com/cgi-bin/token",
        params={"grant_type": "client_credential", "appid": app_id, "secret": app_secret}, timeout=30)
    tok = r.json().get("access_token")
    if not tok:
        raise Exception(f"获取 access_token 失败: {r.json()}")
    return tok


def upload_image_material(app_id, app_secret, image_path):
    """上传永久图片素材（进素材库·图片分类 type=image），返回 media_id+url。"""
    from retry_util import request_with_retry
    tok = _get_token(app_id, app_secret)
    url = f"https://api.weixin.qq.com/cgi-bin/material/add_material?access_token={tok}&type=image"
    with open(image_path, 'rb') as f:
        files = {"media": (os.path.basename(image_path), f, "image/jpeg")}
        r = request_with_retry('POST', url, files=files, timeout=60)
    data = r.json()
    if data.get("errcode", 0) != 0:
        raise Exception(f"素材上传失败: {data}")
    if not data.get("media_id"):
        raise Exception(f"素材上传未返回 media_id: {data}")
    return data  # {media_id, url, ...}


# ---------- 小程序文字链（2026-10-01 起） ----------
# 关键：只有「图文消息」(news) 的 content 支持 HTML，才能放可点击的小程序文字链；
# 「图片消息」(newspic) 的 content 只支持纯文本，写 #小程序:// 也点不动（实测）。
MP_APPID = "wx489060715b335aaf"
MP_PATH = "pages/index/index"
MP_NICKNAME = "棱镜图库"
LINK_TEXT = "高清原图看这里👉 这组图真的每一张都能当壁纸！"


def _link_html():
    """正文末尾那行小程序文字链（整行可点击跳小程序）。"""
    return (
        f'<p><a data-miniprogram-appid="{MP_APPID}" '
        f'data-miniprogram-path="{MP_PATH}" '
        f'data-miniprogram-nickname="{MP_NICKNAME}" '
        f'data-miniprogram-type="text" href="">{LINK_TEXT}</a></p>'
    )


def _shrink_for_upload(src, dst, max_kb=900):
    """uploadimg 对大小敏感，压到 max_kb 以内（不动画质太多）。"""
    from PIL import Image
    im = Image.open(src).convert("RGB")
    q = 90
    im.save(dst, "JPEG", quality=q)
    while os.path.getsize(dst) > max_kb * 1024 and q > 50:
        q -= 10
        im.save(dst, "JPEG", quality=q)
    if os.path.getsize(dst) > max_kb * 1024:
        w, h = im.size
        im = im.resize((int(w * 0.7), int(h * 0.7)), Image.LANCZOS)
        im.save(dst, "JPEG", quality=80)
    return dst


def _draft_content(topic):
    """正文 HTML：图片在上，小程序文字链在末尾（图片由调用方拼在前面）。"""
    return _link_html()


def upload_content_image(app_id, app_secret, image_path):
    """上传正文内图片（uploadimg 接口），返回 mmbiz.qpic.cn URL。

    news 正文里的 <img> 必须用本接口的 URL，素材库的永久素材 URL 会被过滤。
    """
    from retry_util import request_with_retry
    tok = _get_token(app_id, app_secret)
    url = f"https://api.weixin.qq.com/cgi-bin/media/uploadimg?access_token={tok}"
    with open(image_path, "rb") as f:
        files = {"media": (os.path.basename(image_path), f, "image/jpeg")}
        r = request_with_retry('POST', url, files=files, timeout=120)
    data = r.json()
    if not data.get("url"):
        raise Exception(f"正文图片上传失败: {data}")
    return data["url"]


def create_news_draft(app_id, app_secret, title, content_html, thumb_media_id):
    """建「图文消息」草稿（article_type=news）。"""
    from retry_util import request_with_retry
    tok = _get_token(app_id, app_secret)
    article = {
        "article_type": "news",
        "title": title,
        "content": content_html,
        "thumb_media_id": thumb_media_id,
        "need_open_comment": 0,
        "only_fans_can_comment": 0,
    }
    url = f"https://api.weixin.qq.com/cgi-bin/draft/add?access_token={tok}"
    r = request_with_retry('POST', url,
        data=json.dumps({"articles": [article]}, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"}, timeout=60)
    data = r.json()
    if data.get("errcode", 0) != 0:
        raise Exception(f"建图文消息草稿失败: {data}")
    return data


def create_newspic_draft(app_id, app_secret, title, image_media_ids, content=""):
    """建「图片消息」草稿（草稿箱里的贴图，article_type=newspic）。"""
    from retry_util import request_with_retry
    tok = _get_token(app_id, app_secret)
    if len(image_media_ids) > 20:
        image_media_ids = image_media_ids[:20]
    article = {
        "article_type": "newspic",
        "title": title,
        "content": content,
        "need_open_comment": 0,
        "only_fans_can_comment": 0,
        "image_info": {
            "image_list": [{"image_media_id": mid} for mid in image_media_ids]
        },
    }
    url = f"https://api.weixin.qq.com/cgi-bin/draft/add?access_token={tok}"
    r = request_with_retry('POST', url,
        data=json.dumps({"articles": [article]}, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"}, timeout=30)
    data = r.json()
    if data.get("errcode", 0) != 0:
        raise Exception(f"建图片消息草稿失败: {data}")
    return data  # {media_id}


def main():
    ap = argparse.ArgumentParser(description="每小时公众号图集草稿（Pexels 9图→翻转滤镜→贴图草稿，md5去重）")
    ap.add_argument("--topic", default=None, help="指定话题（默认随机）")
    ap.add_argument("--count", type=int, default=9, help="图片数量（默认9）")
    ap.add_argument("--dry-run", action="store_true", help="只下载处理不上传不建草稿")
    args = ap.parse_args()

    if args.topic:
        topic, query = args.topic, args.topic
        for cn, en in TOPICS:
            if cn == args.topic:
                query = en
                break
    else:
        # 话题级去重：当天已用话题不再选，全部用完则重置循环
        used_today = load_topic_day().get(datetime.now().strftime("%Y-%m-%d"), {}).get("topics", [])
        available = [t for t in TOPICS if t[0] not in used_today]
        if not available:
            print(f"!!! 当天 {len(used_today)} 个话题已全部用过，重置循环", file=sys.stderr)
            available = TOPICS
        # 台账感知（2026-09-14 修复）：已发图片多的话题（Pexels 检索深度被吃穿）降权排除
        topic_used = load_topic_usage(load_ledger())
        fresh = [t for t in available if topic_used.get(t[0], 0) < TOPIC_EXHAUSTED]
        if fresh:
            available = fresh
        else:
            print(f"!!! 所有候选话题均已发 ≥{TOPIC_EXHAUSTED} 张，放宽限制", file=sys.stderr)
        topic, query = random.choice(available)
    print(f"话题: {topic}  (Pexels 查询: {query})", file=sys.stderr)

    sent = load_ledger()
    sent_set = set(sent["list"])
    print(f"台账已有 {len(sent_set)} 个已发 md5", file=sys.stderr)

    workdir = tempfile.mkdtemp(prefix="pexels_gallery_")
    # 用户可见输出目录：每次产出落盘 /tmp/gallery_out_<时间戳>/
    save_dir = os.path.join("/tmp", f"gallery_out_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    os.makedirs(save_dir, exist_ok=True)
    try:
        # 每次随机取横图或竖图
        ori = random.choice(["landscape", "portrait"])
        print(f"方向: {ori}", file=sys.stderr)
        # 1. 搜索 + 下载(跳过已发 md5 的重复图，多取候选补足)
        photos = pexels_search(query, per_page=args.count * 4, orientation=ori)
        if len(photos) < args.count * 2:
            photos += pexels_search(TOPICS[0][1], per_page=args.count * 3, orientation=ori)  # 兜底秋天池
        picked = []   # [(path, md5, pexels_id)]
        skipped = 0
        for p in photos:
            if len(picked) >= args.count:
                break
            # 只收符合本次随机方向的图
            if ori == "landscape" and p.get("width", 0) < p.get("height", 0):
                continue
            if ori == "portrait" and p.get("width", 0) >= p.get("height", 0):
                continue
            out = os.path.join(workdir, f"raw_{len(picked)+1}.jpg")
            try:
                pexels_fetch(p["id"], out, original_url=p.get("src", {}).get("original"))
            except Exception as e:
                print(f"  ! 下载失败 {p['id']}: {e}", file=sys.stderr)
                continue
            h = md5_file(out)
            if h in sent_set:
                skipped += 1
                print(f"  ! 剔除重复 md5={h[:12]} (pexels {p['id']})", file=sys.stderr)
                os.remove(out)
                continue
            # 原图落盘到 save_dir（不压缩，用户可见）
            raw_out = os.path.join(save_dir, f"raw_{len(picked)+1}.jpg")
            shutil.copy(out, raw_out)
            picked.append((out, h, p["id"]))
            print(f"  + 下载 pexels {p['id']} md5={h[:12]} ({os.path.getsize(out)//1024}KB)", file=sys.stderr)
        if len(picked) < 3:
            raise Exception(f"去重后有效图片不足3张（仅{len(picked)}张，剔除{skipped}张重复），放弃本次")

        # 2. 左右翻转 + 滤镜 → 产出两版：压缩版（≤600KB，草稿箱）+ 全尺寸版（不压缩，发微信）
        processed = []   # [(final_path, md5, pexels_id)]
        full_size = []   # [(full_path, md5, pexels_id)]  不压缩版
        for i, (src, h, pid) in enumerate(picked):
            dst = os.path.join(workdir, f"proc_{i+1}.jpg")
            process_image(src, dst)
            # 全尺寸版：翻转滤镜后直接存，不压缩
            full_dst = os.path.join(save_dir, f"full_{i+1}.jpg")
            shutil.copy(dst, full_dst)
            full_size.append((full_dst, h, pid))
            # 压缩版
            c_dst = os.path.join(workdir, f"final_{i+1}.jpg")
            compress_image.compress_image(dst, c_dst, max_size_kb=600)
            processed.append((c_dst, h, pid))
        print(f"处理完成 {len(processed)} 张（翻转+滤镜，压缩≤600KB + 全尺寸不压缩各一份，剔除{skipped}张重复）", file=sys.stderr)

        if args.dry_run:
            print(json.dumps({"dry_run": True, "topic": topic,
                              "files": [p for p, _, _ in processed],
                              "skipped_dup": skipped}, ensure_ascii=False, indent=2))
            return

        # 3. 上传：封面（永久素材 → thumb_media_id）+ 正文图（uploadimg → URL）
        cfg = wc_config.get_wechat_config()
        app_id, app_secret = cfg["app_id"], cfg["app_secret"]
        if not app_id or not app_secret:
            raise Exception("微信 .env 配置缺失")

        # 封面：用第 1 张压缩图（永久素材，≤600KB 稳过 2M 限制）
        thumb_res = upload_image_material(app_id, app_secret, processed[0][0])
        thumb_media_id = thumb_res.get("media_id")
        if not thumb_media_id:
            raise Exception(f"封面上传未返回 media_id: {thumb_res}")
        print(f"封面上传 OK media_id={thumb_media_id}", file=sys.stderr)

        # 正文图：用 full_* 压到 ≤900KB 走 uploadimg（比草稿箱那版清晰）
        content_urls = []   # [(url, md5, pexels_id)]
        uploaded = []       # [(md5, pexels_id)] 台账用
        for i, (fp, h, pid) in enumerate(full_size, 1):
            small = os.path.join(workdir, f"up_{i}.jpg")
            try:
                _shrink_for_upload(fp, small)
                u = upload_content_image(app_id, app_secret, small)
            except Exception as e:
                print(f"  ! 正文图 {i} 上传失败: {e}", file=sys.stderr)
                continue
            content_urls.append((u, h, pid))
            uploaded.append((h, pid))
            print(f"  + 正文图 {i} OK ({os.path.getsize(small)//1024}KB)", file=sys.stderr)
        if not content_urls:
            raise Exception("正文图片全部上传失败")
        print(f"正文图上传 OK {len(content_urls)} 张（uploadimg）", file=sys.stderr)

        # 4. 建「图文消息」草稿（news），标题格式：话题·每日图集（日期）
        #    只有 news 的 content 支持 HTML → 那行字才是可点击的小程序链接
        today_str = datetime.now().strftime("%Y-%m-%d")
        title = f"{topic}·每日图集（{today_str}）"
        # 图片之间、以及最后小程序链接之前，各留一个空行（微信里用空段落实现）
        blocks = [f'<p><img src="{u}" style="width:100%;"/></p>' for u, _, _ in content_urls]
        blocks.append(_draft_content(topic))
        content = '<p><br/></p>'.join(blocks)
        draft_res = create_news_draft(app_id, app_secret, title, content, thumb_media_id)
        draft_media_id = draft_res.get("media_id")
        if not draft_media_id:
            raise Exception(f"建图文消息草稿失败: {draft_res}")
        print(f"图文消息草稿 OK media_id={draft_media_id}（正文{len(content_urls)}图+小程序文字链）", file=sys.stderr)

        # 4b. 采集图片尺寸（用于云数据库记录）
        from PIL import Image as _PILImage
        image_dims = []
        for f, h, pid in processed:
            try:
                with _PILImage.open(f) as im:
                    image_dims.append((im.width, im.height))
            except Exception:
                image_dims.append((0, 0))

        # 4c. 小程序云存储转存：原图(full_*) + 缩略图(final_*) → COS + 数据库
        cloud_records = cloud_stash(save_dir, workdir, topic, title, image_dims)
        if cloud_records:
            print(f"☁ 小程序云转存完成 {len(cloud_records)} 张", file=sys.stderr)
        else:
            print(f"⚠ 小程序云转存全部失败（已忽略，不影响主流程）", file=sys.stderr)

        # 5. 草稿成功后才记录 md5 台账 + 当天话题
        record_sent([{"md5": h, "pexels_id": pid, "topic": topic} for h, pid in uploaded])
        record_topic_day(topic)

        # 6. 追加日志
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(os.path.join(LOG_DIR, "gallery_draft.log"), "a", encoding="utf-8") as f:
            f.write(f"{datetime.now().isoformat()} | {title} | 正文图{len(content_urls)}张 | "
                    f"草稿media_id={draft_media_id} | type=news\n")

        # stdout 供 cron 汇报
        full_files = sorted(glob.glob(os.path.join(save_dir, "full_*.jpg")))
        print(json.dumps({
            "status": "success",
            "topic": topic,
            "images": len(content_urls),
            "article_type": "news",
            "skipped_dup": skipped,
            "title": title,
            "media_id": draft_media_id,
            "thumb_media_id": thumb_media_id,
            "save_dir": save_dir,
            "full_images": [os.path.basename(f) for f in full_files],
            "cloud_records": cloud_records,
        }, ensure_ascii=False, indent=2))
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


# ============================================================
# 小程序云环境：云存储转存 + 数据库记录
# ============================================================

CLOUD_APPID = "wx489060715b335aaf"
CLOUD_SECRET = "fad6d8897931fb0a741209c96fc563a8"
CLOUD_ENV = "cloud1-d9gkyv32i776bf4cc"
CLOUD_TOKEN_CACHE = {"token": None, "expires_at": 0}

# 话题 → 标签映射（一对多，按图集关键词匹配）
TOPIC_TAG_MAP = {
    # 自然景观
    "秋天": ["风景"], "秋叶": ["风景"], "雪景": ["风景"], "星空": ["风景", "星空"],
    "大海": ["风景", "旅行"], "森林": ["风景"], "花朵": ["风景", "植物"],
    "日出": ["风景"], "城市夜景": ["风景", "旅行"], "山川": ["风景"],
    "春天": ["风景", "植物"], "夏日": ["风景", "旅行"], "黄昏": ["风景"],
    "湖泊": ["风景"], "沙漠": ["风景", "旅行"], "极光": ["风景", "星空"],
    "云海": ["风景"], "溪流": ["风景"],
    "梯田": ["风景", "旅行"], "峡谷": ["风景"], "瀑布": ["风景"],
    "湿地": ["风景", "植物"], "草原": ["风景"],
    "秋林小径": ["风景"], "雾凇": ["风景"], "盐湖": ["风景"],
    "火山口": ["风景"], "冰川": ["风景"], "雨林": ["风景", "植物"],
    "荷塘": ["风景", "植物"], "海边落日": ["风景", "旅行"],
    "梯田晨雾": ["风景", "旅行"],
    # 建筑
    "古镇小桥流水": ["建筑", "旅行"], "摩天大楼": ["建筑", "科技"],
    "现代建筑": ["建筑"], "古建筑": ["建筑"], "教堂": ["建筑"],
    "桥梁": ["建筑"], "吊桥": ["建筑"], "灯塔": ["建筑"],
    "风车": ["建筑"], "水乡古镇": ["建筑", "旅行"],
    "城堡": ["建筑"], "高楼窗景": ["建筑"], "街头巷弄": ["建筑"],
    "图书馆": ["建筑"], "车站": ["建筑"], "庭院": ["建筑"],
    "老城区": ["建筑", "旅行"], "玻璃幕墙": ["建筑"],
    "天台视角": ["建筑"], "胡同人家": ["建筑"],
    "石库门": ["建筑"], "徽派民居": ["建筑"],
    "窑洞": ["建筑"], "客家土楼": ["建筑"],
    "栈桥": ["建筑"], "缆车": ["建筑", "旅行"],
    "夜市": ["旅行"], "地下通道": ["建筑"],
    # 世界地标/古迹
    "古迹遗址": ["建筑", "旅行"], "雅典卫城": ["建筑", "旅行"],
    "吴哥窟": ["建筑", "旅行"], "马丘比丘": ["建筑", "旅行"],
    "巨石阵": ["建筑", "旅行"], "帕特农神庙": ["建筑", "旅行"],
    "比萨斜塔": ["建筑", "旅行"], "科隆大教堂": ["建筑"],
    "圣家堂": ["建筑"], "米兰大教堂": ["建筑"],
    "摩索拉斯陵墓": ["建筑"], "长城": ["建筑", "旅行"],
    "故宫": ["建筑", "旅行"], "天坛": ["建筑"],
    "西湖": ["风景", "旅行"], "黄山": ["风景", "旅行"],
    "桂林山水": ["风景", "旅行"], "张家界": ["风景", "旅行"],
    "九寨沟": ["风景", "旅行"], "布达拉宫": ["建筑", "旅行"],
    "兵马俑": ["建筑"], "敦煌莫高窟": ["建筑"],
    "外滩": ["建筑", "旅行"], "东方明珠": ["建筑"],
    "上海陆家嘴": ["建筑"], "广州塔": ["建筑"],
    "云南洱海": ["风景", "旅行"], "稻城亚丁": ["风景", "旅行"],
    "喀纳斯": ["风景", "旅行"], "埃菲尔铁塔": ["建筑", "旅行"],
    "金字塔": ["建筑", "旅行"], "泰姬陵": ["建筑", "旅行"],
    "富士山": ["风景", "旅行"], "圣托里尼": ["风景", "旅行"],
    "威尼斯": ["建筑", "旅行"], "罗马斗兽场": ["建筑"],
    "悉尼歌剧院": ["建筑"], "自由女神": ["建筑"],
    "里约基督像": ["建筑"], "佩特拉古城": ["建筑", "旅行"],
    "黄石公园": ["风景", "旅行"], "大峡谷": ["风景", "旅行"],
    "尼亚加拉瀑布": ["风景", "旅行"], "阿尔卑斯山": ["风景", "旅行"],
    "马尔代夫": ["风景", "旅行"], "巴厘岛": ["风景", "旅行"],
    "布拉格": ["建筑", "旅行"], "阿姆斯特丹": ["建筑", "旅行"],
    "冰岛黑沙滩": ["风景", "旅行"], "挪威峡湾": ["风景", "旅行"],
    "土耳其热气球": ["旅行"], "撒哈拉沙漠": ["风景", "旅行"],
    "日月潭": ["风景", "旅行"], "呼伦贝尔": ["风景", "旅行"],
    "青海湖": ["风景", "旅行"], "泰山": ["风景", "旅行"],
    "华山": ["风景", "旅行"], "峨眉山": ["风景", "旅行"],
    "武当山": ["风景", "旅行"], "平遥古城": ["建筑", "旅行"],
    "凤凰古城": ["建筑", "旅行"], "婺源": ["风景", "旅行"],
    "宏村": ["建筑", "旅行"], "泸沽湖": ["风景", "旅行"],
    "香格里拉": ["风景", "旅行"], "拉萨": ["建筑", "旅行"],
    "香港夜景": ["建筑", "旅行"], "台北101": ["建筑"],
    "新加坡滨海湾": ["建筑", "旅行"], "迪拜塔": ["建筑"],
    "吴哥日出": ["建筑", "旅行"], "雅典神庙": ["建筑", "旅行"],
    # 人文生活
    "阅读": ["人像"], "咖啡馆": ["人像"], "街头摄影师": ["人像"],
    "茶室": ["人像"], "书店": ["建筑"], "集市": ["旅行"],
    "雨天街道": ["旅行"], "夜景人像": ["人像"],
    "帐篷露营": ["旅行"], "滑雪": ["运动", "旅行"],
    "海滩日光浴": ["旅行"], "手艺市集": ["旅行"],
    "街头演出": ["旅行"], "晨跑": ["运动"],
    "垂钓": ["旅行"], "登山者": ["运动", "旅行"],
    "家庭厨房": ["人像"], "街头小吃摊": ["美食", "旅行"],
    "露营篝火": ["旅行"], "陶艺工坊": ["人像"],
    "木工坊": ["人像"],
}


def _get_cloud_token():
    """获取小程序云开发 access_token（带缓存，提前 5 分钟刷新）"""
    now = time.time()
    if CLOUD_TOKEN_CACHE["token"] and now < CLOUD_TOKEN_CACHE["expires_at"] - 300:
        return CLOUD_TOKEN_CACHE["token"]
    r = requests.get(
        "https://api.weixin.qq.com/cgi-bin/token",
        params={"grant_type": "client_credential", "appid": CLOUD_APPID, "secret": CLOUD_SECRET},
        timeout=15,
    )
    data = r.json()
    tok = data.get("access_token")
    if not tok:
        raise Exception(f"云开发 token 获取失败: {data}")
    CLOUD_TOKEN_CACHE["token"] = tok
    CLOUD_TOKEN_CACHE["expires_at"] = now + data.get("expires_in", 7200)
    return tok


def upload_to_cloud(image_path, cloud_path):
    """上传图片到小程序云存储，返回 file_id。

    cloud_path: 云存储路径，如 'images/original/1790320786526-abc123.jpg'
    """
    tok = _get_cloud_token()
    # 1. 获取上传凭证
    r = requests.post(
        f"https://api.weixin.qq.com/tcb/uploadfile?access_token={tok}",
        json={"env": CLOUD_ENV, "path": cloud_path}, timeout=15,
    )
    info = r.json()
    if info.get("errcode") != 0:
        raise Exception(f"云存储获取上传凭证失败: {info}")
    # 2. 上传到 COS
    with open(image_path, "rb") as f:
        files = {
            "key": (None, cloud_path),
            "Signature": (None, info["authorization"]),
            "x-cos-security-token": (None, info["token"]),
            "x-cos-meta-fileid": (None, info["cos_file_id"]),
            "file": (os.path.basename(image_path), f, "image/jpeg"),
        }
        up = requests.post(info["url"], files=files, timeout=60)
    if up.status_code not in (200, 204):
        raise Exception(f"云存储 COS 上传失败: HTTP {up.status_code} {up.text[:200]}")
    return info["file_id"]


def record_image_to_db(title, category, original_file_id, thumbnail_file_id,
                       width, height, tags=None, categories=None):
    """向小程序云数据库 images 集合插入一条图片记录。"""
    if tags is None:
        tags = []
    if categories is None:
        categories = [category] if category else []
    tok = _get_cloud_token()
    now_ms = int(time.time() * 1000)
    parts = [
        "db.collection('images').add({",
        "data: [{",
        "title: " + json.dumps(title, ensure_ascii=False) + ",",
        "category: " + json.dumps(category, ensure_ascii=False) + ",",
        "categories: " + json.dumps(categories, ensure_ascii=False) + ",",
        "tags: " + json.dumps(tags, ensure_ascii=False) + ",",
        "originalFileID: " + json.dumps(original_file_id) + ",",
        "thumbnailFileID: " + json.dumps(thumbnail_file_id) + ",",
        "width: " + str(width) + ",",
        "height: " + str(height) + ",",
        "uploadTime: new Date(" + str(now_ms) + "),",
        "downloads: 0, status: 1, reviewer: '', reviewTime: null",
        "}]})"
    ]
    q = " ".join(parts)
    r = requests.post(
        f"https://api.weixin.qq.com/tcb/databaseadd?access_token={tok}",
        json={"env": CLOUD_ENV, "query": q},
        timeout=15,
    )
    data = r.json()
    if data.get("errcode") != 0:
        raise Exception(f"云数据库写入失败: {data}")
    return data.get("id_list", [None])[0]


def cloud_stash(orig_dir, thumb_dir, topic, title, image_widths_heights, tags=None):
    """把一批处理好的图片转存到小程序云存储 + 写数据库。

    orig_dir: 包含 full_*.jpg（全尺寸/原图）的目录
    thumb_dir: 包含 final_*.jpg（压缩版/缩略图）的目录
    image_widths_heights: 与图片一一对应的 [(width, height), ...]，按 final_1, final_2 顺序
    tags: 标签列表，如不传则从 TOPIC_TAG_MAP 按 topic 自动匹配

    返回: [(original_file_id, thumbnail_file_id, _id), ...]
    """
    if tags is None:
        tags = TOPIC_TAG_MAP.get(topic, [topic])
    category = tags[0] if tags else topic
    categories = tags
    results = []
    ts = int(time.time() * 1000)
    for i, (w, h) in enumerate(image_widths_heights, start=1):
        short = hashlib.md5(f"{ts}-{i}".encode()).hexdigest()[:8]
        orig_path = os.path.join(orig_dir, f"full_{i}.jpg")
        thumb_path = os.path.join(thumb_dir, f"final_{i}.jpg")
        if not os.path.exists(orig_path) or not os.path.exists(thumb_path):
            print(f"  ! 云转存跳过第 {i} 张（文件缺失）", file=sys.stderr)
            continue
        # 原图路径：images/original/
        orig_cloud_path = f"images/original/{ts}-{short}.jpg"
        thumb_cloud_path = f"images/thumbnails/{ts}-{short}.jpg"
        try:
            orig_fid = upload_to_cloud(orig_path, orig_cloud_path)
            thumb_fid = upload_to_cloud(thumb_path, thumb_cloud_path)
            rec_id = record_image_to_db(title, category, orig_fid, thumb_fid, w, h, tags=tags, categories=categories)
            results.append((orig_fid, thumb_fid, rec_id))
            print(f"  ☁ 云转存 OK #{i}: orig={orig_fid} thumb={thumb_fid} db_id={rec_id} tags={tags}", file=sys.stderr)
        except Exception as e:
            print(f"  ! 云转存失败 #{i}: {e}", file=sys.stderr)
    return results


if __name__ == "__main__":
    main()