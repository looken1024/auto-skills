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
import os, sys, json, random, shutil, argparse, tempfile, hashlib
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
import config as wc_config
import compress_image

# ---------- 话题池：中文名 → Pexels 英文搜索词 ----------
TOPICS = [
    # --- 自然景观 ---
    ("秋天", "autumn forest"),
    ("秋天", "autumn leaves"),
    ("雪景", "winter snow landscape"),
    ("星空", "starry night sky"),
    ("大海", "ocean waves sunset"),
    ("森林", "green forest sunlight"),
    ("花朵", "flower meadow"),
    ("日出", "sunrise mountains"),
    ("城市夜景", "city night lights"),
    ("山川", "mountain landscape fog"),
    ("春天", "spring blossom trees"),
    ("夏日", "summer beach"),
    ("黄昏", "sunset sky clouds"),
    ("湖泊", "lake reflection mountains"),
    ("沙漠", "desert dunes"),
    ("极光", "aurora borealis"),
    ("云海", "sea of clouds"),
    ("溪流", "mountain stream waterfall"),
    # --- 交通工具 ---
    ("汽车", "classic car highway"),
    ("跑车", "sports car speed"),
    ("火车", "train railway track"),
    ("高铁", "high speed train"),
    ("飞机", "airplane wing sky"),
    ("直升机", "helicopter flight"),
    ("轮船", "ship ocean sailing"),
    ("帆船", "sailboat sea"),
    ("摩托车", "motorcycle road trip"),
    ("自行车", "bicycle city street"),
    ("地铁", "subway station"),
    ("热气球", "hot air balloon sky"),
    ("赛车", "race car track"),
    ("卡车", "truck mountain road"),
    ("游艇", "yacht sea luxury"),
    ("古镇小桥流水", "ancient boat river town"),
    # --- 建筑 ---
    ("摩天大楼", "skyscraper city"),
    ("现代建筑", "modern architecture"),
    ("古建筑", "ancient architecture temple"),
    ("教堂", "cathedral church architecture"),
    ("桥梁", "bridge architecture"),
    ("吊桥", "suspension bridge"),
    ("灯塔", "lighthouse coast"),
    ("风车", "windmill countryside"),
    ("水乡古镇", "chinese ancient town"),
    ("城堡", "castle europe"),
    ("高楼窗景", "city skyline reflection"),
    ("街头巷弄", "old street alley"),
    ("图书馆", "library interior"),
    ("车站", "train station architecture"),
    ("庭院", "courtyard garden architecture"),
    # --- 动物 ---
    ("猫咪", "cat closeup"),
    ("狗狗", "dog portrait"),
    ("鸟类", "birds in flight"),
    ("狮子", "lion wildlife"),
    ("老虎", "tiger wildlife"),
    ("大象", "elephant savanna"),
    ("长颈鹿", "giraffe wildlife"),
    ("猴子", "monkey forest"),
    ("熊猫", "panda bamboo"),
    ("鹿", "deer forest nature"),
    ("狐狸", "fox wildlife"),
    ("海豚", "dolphin ocean"),
    ("鲸鱼", "whale ocean"),
    ("蝴蝶", "butterfly flower"),
    ("马", "horse running pasture"),
    ("羊驼", "alpaca farm"),
    ("雪鸮", "snowy owl"),
    # --- 美食 ---
    ("美食", "delicious food table"),
    ("烘焙", "fresh baked bread"),
    ("咖啡", "coffee latte art"),
    ("水果", "fresh fruit market"),
    ("寿司", "sushi japanese food"),
    ("茶", "tea ceremony"),
    ("甜点", "dessert cake"),
    # --- 人文生活 ---
    ("阅读", "reading book cozy"),
    ("咖啡馆", "coffee shop interior"),
    ("街头摄影师", "street photography city"),
    ("茶室", "teahouse interior"),
    ("书店", "bookstore shelves"),
    ("集市", "farmers market stalls"),
    ("雨天街道", "rainy street umbrella"),
    ("夜景人像", "city night person silhouette"),
    ("帐篷露营", "camping tent stars"),
    ("滑雪", "skiing snow mountain"),
    ("海滩日光浴", "beach vacation relax"),
    # --- 景点地标 ---
    ("长城", "great wall of china"),
    ("故宫", "forbidden city beijing"),
    ("天坛", "temple of heaven beijing"),
    ("西湖", "west lake hangzhou"),
    ("黄山", "huangshan mountain"),
    ("桂林山水", "guilin karst landscape"),
    ("张家界", "zhangjiajie national forest park"),
    ("九寨沟", "jiuzhaigou valley"),
    ("布达拉宫", "potala palace lhasa"),
    ("兵马俑", "terracotta warriors"),
    ("敦煌莫高窟", "mogao caves dunhuang"),
    ("外滩", "the bund shanghai skyline"),
    ("东方明珠", "oriental pearl tower shanghai"),
    ("上海陆家嘴", "lujiazui financial district"),
    ("广州塔", "canton tower guangzhou"),
    ("云南洱海", "erhai lake dali"),
    ("稻城亚丁", "yading nature reserve"),
    ("喀纳斯", "kanas lake xinjiang"),
    ("埃菲尔铁塔", "eiffel tower paris"),
    ("金字塔", "pyramids of giza"),
    ("泰姬陵", "taj mahal"),
    ("富士山", "mount fuji japan"),
    ("圣托里尼", "santorini greece"),
    ("威尼斯", "venice canals italy"),
    ("罗马斗兽场", "colosseum rome"),
    ("悉尼歌剧院", "sydney opera house"),
    ("自由女神", "statue of liberty"),
    ("大本钟", "big ben london"),
    ("里约基督像", "christ the redeemer rio"),
    ("佩特拉古城", "petra jordan"),
]

PEXELS_CFG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..",
                          "douyin-card-pipeline", "config.json")
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs")
LEDGER_FILE = os.path.join(LOG_DIR, "gallery_sent_md5.json")
TOPIC_DAY_FILE = os.path.join(LOG_DIR, "gallery_topic_day.json")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"}


# ---------- 话题级去重（同一天不重复选话题） ----------
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


def pexels_search(query, per_page=40):
    import urllib.request, urllib.parse
    key = get_pexels_key()
    url = "https://api.pexels.com/v1/search?query=%s&per_page=%d&orientation=landscape" % (
        urllib.parse.quote(query), per_page)
    req = urllib.request.Request(url, headers={"Authorization": key, **UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read()).get("photos", [])


def pexels_fetch(photo_id, out):
    import urllib.request
    url = ("https://images.pexels.com/photos/%d/pexels-photo-%d.jpeg"
           "?auto=compress&cs=tinysrgb&w=1920&h=1080&fit=crop" % (photo_id, photo_id))
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    with open(out, "wb") as f:
        f.write(data)
    return out


def process_image(src, dst):
    """左右翻转 + 滤镜（对比度/色彩/亮度微调）+ 轻噪点，不叠字。"""
    from PIL import Image, ImageEnhance
    import numpy as np
    im = Image.open(src).convert("RGB")
    im = im.transpose(Image.FLIP_LEFT_RIGHT)
    im = ImageEnhance.Contrast(im).enhance(random.uniform(1.05, 1.12))
    im = ImageEnhance.Color(im).enhance(random.uniform(0.95, 1.08))
    im = ImageEnhance.Brightness(im).enhance(random.uniform(0.98, 1.05))
    # 轻噪点（方差 2-3.5）打散指纹
    arr = np.array(im).astype(np.int16)
    noise = np.random.normal(0, random.uniform(2.0, 3.5), arr.shape)
    arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
    im = Image.fromarray(arr)
    im.save(dst, "JPEG", quality=88)
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
        topic, query = random.choice(available)
    print(f"话题: {topic}  (Pexels 查询: {query})", file=sys.stderr)

    sent = load_ledger()
    sent_set = set(sent["list"])
    print(f"台账已有 {len(sent_set)} 个已发 md5", file=sys.stderr)

    workdir = tempfile.mkdtemp(prefix="pexels_gallery_")
    try:
        # 1. 搜索 + 下载(跳过已发 md5 的重复图，多取候选补足)
        photos = pexels_search(query, per_page=args.count * 4)
        if len(photos) < args.count * 2:
            photos += pexels_search(TOPICS[0][1], per_page=args.count * 3)  # 兜底秋天池
        picked = []   # [(path, md5, pexels_id)]
        skipped = 0
        for p in photos:
            if len(picked) >= args.count:
                break
            if p.get("width", 0) < p.get("height", 0):  # 只收横图
                continue
            out = os.path.join(workdir, f"raw_{len(picked)+1}.jpg")
            try:
                pexels_fetch(p["id"], out)
            except Exception as e:
                print(f"  ! 下载失败 {p['id']}: {e}", file=sys.stderr)
                continue
            h = md5_file(out)
            if h in sent_set:
                skipped += 1
                print(f"  ! 剔除重复 md5={h[:12]} (pexels {p['id']})", file=sys.stderr)
                os.remove(out)
                continue
            picked.append((out, h, p["id"]))
            print(f"  + 下载 pexels {p['id']} md5={h[:12]} ({os.path.getsize(out)//1024}KB)", file=sys.stderr)
        if len(picked) < 3:
            raise Exception(f"去重后有效图片不足3张（仅{len(picked)}张，剔除{skipped}张重复），放弃本次")

        # 2. 左右翻转 + 滤镜 + 压缩
        processed = []   # [(final_path, md5, pexels_id)]
        for i, (src, h, pid) in enumerate(picked):
            dst = os.path.join(workdir, f"proc_{i+1}.jpg")
            process_image(src, dst)
            c_dst = os.path.join(workdir, f"final_{i+1}.jpg")
            compress_image.compress_image(dst, c_dst, max_size_kb=600)
            processed.append((c_dst, h, pid))
        print(f"处理完成 {len(processed)} 张（翻转+滤镜+压缩≤600KB，剔除{skipped}张重复）", file=sys.stderr)

        if args.dry_run:
            print(json.dumps({"dry_run": True, "topic": topic,
                              "files": [p for p, _, _ in processed],
                              "skipped_dup": skipped}, ensure_ascii=False, indent=2))
            return

        # 3. 上传永久图片素材
        cfg = wc_config.get_wechat_config()
        app_id, app_secret = cfg["app_id"], cfg["app_secret"]
        if not app_id or not app_secret:
            raise Exception("微信 .env 配置缺失")

        media_ids = []
        uploaded = []   # [(md5, pexels_id)]
        for f, h, pid in processed:
            try:
                res = upload_image_material(app_id, app_secret, f)
            except Exception as e:
                print(f"  ! 素材上传失败 {f}: {e}", file=sys.stderr)
                continue
            mid = res.get("media_id")
            if not mid:
                print(f"  ! 素材上传未返回 media_id: {f} → {res}", file=sys.stderr)
                continue
            media_ids.append(mid)
            uploaded.append((h, pid))
        if not media_ids:
            raise Exception("全部图片素材上传失败")
        print(f"素材库上传 OK {len(media_ids)} 张（type=image 永久素材）", file=sys.stderr)

        # 4. 建「图片消息」草稿（草稿箱贴图），标题带日期（不含小时分钟）
        now_dt = datetime.now()
        today = now_dt.strftime("%Y-%m-%d")
        title = f"{topic} · 每日图集 ({today})"
        draft_res = create_newspic_draft(app_id, app_secret, title, media_ids)
        draft_media_id = draft_res.get("media_id")
        if not draft_media_id:
            raise Exception(f"建图片消息草稿失败: {draft_res}")
        print(f"图片消息草稿 OK media_id={draft_media_id}", file=sys.stderr)

        # 5. 草稿成功后才记录 md5 台账 + 当天话题
        record_sent([{"md5": h, "pexels_id": pid, "topic": topic} for h, pid in uploaded])
        record_topic_day(topic)

        # 6. 追加日志
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(os.path.join(LOG_DIR, "gallery_draft.log"), "a", encoding="utf-8") as f:
            f.write(f"{datetime.now().isoformat()} | {title} | 素材{len(media_ids)}张 | 草稿media_id={draft_media_id}\n")

        # stdout 供 cron 汇报
        print(json.dumps({
            "status": "success",
            "topic": topic,
            "images": len(media_ids),
            "skipped_dup": skipped,
            "title": title,
            "media_id": draft_media_id,
            "image_media_ids": media_ids,
        }, ensure_ascii=False, indent=2))
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    main()