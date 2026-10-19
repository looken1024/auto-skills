#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
话题池轮换：每 3 天跑一次，剔掉高频话题、从话题银行补入新话题。

规则（2026-10-19 用户指定）：
  - 高频 = 最近 --window-days 天内被选中 ≥2 次，或累计出图 ≥ --life-max 张
  - 剔除后按等量从 topic_bank.json 的 pending 里补新话题
  - 每个新话题先用 Pexels API 验证：横图数量 ≥ --min-results 才入池
  - 银行里验证失败的移入 rejected，成功入池的移入 used，永不重复使用
  - 写入前自动备份 topics.json / topic_bank.json

用法:
  python3 rotate_topics.py                # 正常轮换
  python3 rotate_topics.py --dry-run      # 只算不写
  python3 rotate_topics.py --status       # 只看银行余量/使用情况
  python3 rotate_topics.py --topup-seed N # 预留：手动追加候选（stdin 传 JSON）

输出：stdout 打一段人类可读摘要 + 末尾一行 JSON（供 cron 投递/排查）。
"""
import os, sys, json, argparse, shutil, urllib.request, urllib.parse
from datetime import datetime, timedelta
from collections import Counter

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TOPICS_JSON = os.path.join(SCRIPT_DIR, "topics.json")
BANK_JSON = os.path.join(SCRIPT_DIR, "topic_bank.json")
LOG_DIR = os.path.join(SCRIPT_DIR, "..", "logs")
LEDGER_FILE = os.path.join(LOG_DIR, "gallery_sent_md5.json")
TOPIC_DAY_FILE = os.path.join(LOG_DIR, "gallery_topic_day.json")
PEXELS_CFG = os.path.join(SCRIPT_DIR, "..", "..", "douyin-card-pipeline", "config.json")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"}


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def backup(path):
    if os.path.exists(path):
        bak = path + ".bak-" + datetime.now().strftime("%Y%m%d_%H%M%S")
        shutil.copy2(path, bak)
        return bak
    return None


def pexels_key():
    data = load_json(PEXELS_CFG, {})
    key = data.get("pexels_api_key", "")
    if not key:
        raise RuntimeError("Pexels API key 未配置 (douyin-card-pipeline/config.json)")
    return key


def pexels_count(en, tries=3):
    """返回 (横图数量, 错误信息)"""
    url = ("https://api.pexels.com/v1/search?query=%s&per_page=24&orientation=landscape"
           % urllib.parse.quote(en))
    last = ""
    for _ in range(tries):
        try:
            req = urllib.request.Request(url, headers={"Authorization": pexels_key(), **UA})
            with urllib.request.urlopen(req, timeout=25) as r:
                photos = json.loads(r.read()).get("photos", [])
            return sum(1 for p in photos if p.get("width", 0) > p.get("height", 0)), ""
        except Exception as e:
            last = f"{type(e).__name__}: {e}"[:120]
    return -1, last


def usage_stats(window_days):
    ledger = load_json(LEDGER_FILE, {"md5s": {}})
    md5s = ledger.get("md5s", {}) if isinstance(ledger, dict) else {}
    life = Counter(v.get("topic") for v in md5s.values())
    cut = (datetime.now() - timedelta(days=window_days)).timestamp()
    win = Counter()
    for v in md5s.values():
        ts = v.get("ts")
        try:
            t = datetime.fromisoformat(ts).timestamp() if isinstance(ts, str) else float(ts or 0)
        except Exception:
            t = 0
        if t >= cut:
            win[v.get("topic")] += 1
    return life, win


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--remove-top", type=int, default=30, help="每轮最多剔除多少条（默认30）")
    ap.add_argument("--window-days", type=int, default=3)
    ap.add_argument("--life-max", type=int, default=27, help="累计出图达到该值也算高频（默认27）")
    ap.add_argument("--min-results", type=int, default=12, help="Pexels 横图最低产量")
    ap.add_argument("--max-per-query", type=int, default=3, help="单轮同一英文查询最多验几次")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--status", action="store_true")
    args = ap.parse_args()

    topics = load_json(TOPICS_JSON, [])
    if not isinstance(topics, list) or not topics:
        print(json.dumps({"status": "error", "msg": "topics.json 为空或格式不对"}, ensure_ascii=False))
        return 1

    bank = load_json(BANK_JSON, {})
    if not isinstance(bank, dict):
        bank = {}
    bank.setdefault("pending", [])
    bank.setdefault("rejected", [])
    bank.setdefault("used", [])
    for k in ("pending", "rejected", "used"):
        bank[k] = [x for x in bank.get(k, []) if isinstance(x, dict) and x.get("cn") and x.get("en")]

    life, win = usage_stats(args.window_days)

    if args.status:
        print(f"池子: {len(topics)} 条；银行 pending={len(bank['pending'])} "
              f"used={len(bank['used'])} rejected={len(bank['rejected'])}")
        return 0

    # ---------- 1. 选高频话题剔除 ----------
    def score(t):
        return (win.get(t["cn"], 0), life.get(t["cn"], 0))

    hot = [t for t in topics
           if win.get(t["cn"], 0) >= 2 or life.get(t["cn"], 0) >= args.life_max]
    hot.sort(key=score, reverse=True)
    remove = hot[:args.remove_top]
    remove_cn = {t["cn"] for t in remove}
    kept = [t for t in topics if t["cn"] not in remove_cn]

    need = len(remove)  # 等量补充，保持池子规模稳定
    ever_used = set(life) | {t["cn"] for t in topics}
    used_en = {t["en"] for t in topics} | {x.get("en") for x in bank["used"]} | {x.get("en") for x in bank["rejected"]}

    # ---------- 2. 从银行补新 ----------
    added, rejected_now = [], []
    pending = list(bank["pending"])
    i = 0
    while len(added) < need and i < len(pending):
        cand = pending[i]; i += 1
        cn, en = cand["cn"], cand["en"]
        if cn in ever_used or en in used_en:
            rejected_now.append({**cand, "reason": "历史已用过/重复"})
            continue
        n, err = pexels_count(en)
        if n >= args.min_results:
            added.append(cand)
            ever_used.add(cn); used_en.add(en)
        else:
            rejected_now.append({**cand, "reason": err or f"横图仅{n}张"})
            print(f"  ✗ {cn} 验证失败: {err or f'横图仅{n}张'}", file=sys.stderr)

    # 银行出队
    taken = {x["cn"] for x in added} | {x["cn"] for x in rejected_now}
    bank["pending"] = [x for x in bank["pending"] if x["cn"] not in taken]
    bank["used"] += [{**x, "ts": datetime.now().isoformat()} for x in added]
    bank["rejected"] += rejected_now

    final = kept + [{"cn": x["cn"], "en": x["en"]} for x in added]

    summary = {
        "status": "success",
        "removed": [{"cn": t["cn"], "window": win.get(t["cn"], 0), "life": life.get(t["cn"], 0)}
                    for t in remove],
        "added": [x["cn"] for x in added],
        "added_count": len(added),
        "removed_count": len(remove),
        "topics_before": len(topics),
        "topics_after": len(final),
        "bank_pending": len(bank["pending"]),
        "bank_used": len(bank["used"]),
        "bank_rejected": len(bank["rejected"]),
        "shortfall": max(0, need - len(added)),
    }

    if args.dry_run:
        print(json.dumps({"dry_run": True, **summary}, ensure_ascii=False, indent=2))
        return 0

    # ---------- 3. 落盘 ----------
    b1 = b2 = None
    if remove or added:
        b1 = backup(TOPICS_JSON)
        save_json(TOPICS_JSON, final)
        b2 = backup(BANK_JSON)
        save_json(BANK_JSON, bank)

    print(f"剔除 {len(remove)} 条高频话题：{'、'.join(t['cn'] for t in remove) or '无'}")
    print(f"补入 {len(added)} 条新话题：{'、'.join(x['cn'] for x in added) or '无'}")
    print(f"池子 {len(topics)} → {len(final)} 条；银行余额 pending={len(bank['pending'])}")
    if summary["shortfall"]:
        print(f"⚠️ BANK_LOW：还差 {summary['shortfall']} 条没补上，请补充 topic_bank.json 的 pending")
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
