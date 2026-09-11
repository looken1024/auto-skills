#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
话题池自动补充：每 3 天给 scripts/topics.json 追加一批新话题。

分类（用户 2026-09-11 指定）：风景类、名人类、事件类、景点类、科技类。
- 风景/景点/科技：直接用 Pexels 可搜到的场景词。
- 名人/事件：Pexels 无肖像/新闻授权图，改用「泛化场景词」（红毯、领奖台、发布会、
  火箭发射……），既贴合主题又能搜到横图。

用法:
  python3 expand_topics.py [--per-category 6] [--dry-run]

追加规则：按 cn 去重，已存在的不再加；写回前自动备份。
"""
import os, sys, json, random, argparse, shutil
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TOPICS_JSON = os.path.join(SCRIPT_DIR, "topics.json")

# ---------- 候选池：按类别 ----------
# 结构与 topics.json 一致：[{"cn":..,"en":..}]
CANDIDATES = {
    "风景类": [
        ("梯田晨雾", "rice terraces morning mist"),
        ("海岸悬崖", "coastal cliffs ocean"),
        ("薰衣草田", "lavender field provence"),
        ("油菜花田", "rapeseed flower field"),
        ("白桦林", "birch forest autumn"),
        ("草原晨光", "grassland sunrise prairie"),
        ("雪山日落", "snow mountain sunset alpenglow"),
        ("雨林溪流", "rainforest stream waterfall"),
        ("芦苇荡", "reed marsh wetland autumn"),
        ("火山熔岩", "volcano lava landscape"),
        ("冰川湖", "glacier lake turquoise"),
        ("峡谷落日", "canyon sunset desert"),
        ("红土地", "red earth farmland landscape"),
        ("胡杨林", "poplar forest desert autumn"),
        ("云瀑", "sea of clouds mountain"),
        ("盐湖倒影", "salt flat mirror reflection"),
        ("高山杜鹃", "alpine rhododendron bloom"),
        ("瀑布群落", "waterfall cascade jungle"),
        ("星空银河", "milky way night sky desert"),
        ("极光雪原", "aurora borealis snow field"),
        ("雾漫山峦", "foggy mountain range layers"),
        ("秋日枫林", "maple forest red autumn"),
        ("海蚀地貌", "sea rock coastline erosion"),
        ("湿地候鸟", "wetland migratory birds"),
    ],
    # 名人类：2026-09-11 用户要求去掉，不再补充
    "事件类": [
        ("火箭发射", "rocket launch space"),
        ("航天器组装", "spacecraft assembly clean room"),
        ("奥运赛场", "olympic stadium sports event"),
        ("马拉松", "marathon runners crowd street"),
        ("音乐节现场", "music festival crowd stage"),
        ("电影节", "film festival red carpet press"),
        ("科技发布会", "tech product launch keynote"),
        ("车展", "auto show exhibition cars"),
        ("书展", "book fair exhibition shelves"),
        ("艺术博览会", "art fair exhibition visitors"),
        ("大选投票站", "election voting booth queue"),
        ("峰会论坛", "international summit forum delegates"),
        ("展会人流", "trade show exhibition hall crowd"),
        ("毕业典礼", "graduation ceremony caps gowns"),
        ("阅兵方阵", "military parade formation"),
        ("烟火大会", "fireworks festival night crowd"),
        ("体育颁奖", "sports medal ceremony podium"),
        ("开幕剪彩", "ribbon cutting ceremony opening"),
    ],
    "景点类": [
        ("布拉格老城", "prague old town square"),
        ("阿姆斯特丹运河", "amsterdam canal houses"),
        ("挪威峡湾", "norway fjord cruise"),
        ("冰岛黑沙滩", "iceland black sand beach"),
        ("土耳其棉花堡", "pamukkale terraces turkey"),
        ("马尔代夫环礁", "maldives atoll turquoise water"),
        ("黄石间歇泉", "yellowstone geyser basin"),
        ("尼亚加拉瀑布", "niagara falls panorama"),
        ("大本钟夜景", "big ben night london"),
        ("罗马许愿池", "trevi fountain rome"),
        ("凡尔赛宫", "versailles palace gardens"),
        ("圣托里尼蓝顶", "santorini blue dome church"),
        ("吴哥巴戎寺", "bayon temple angkor faces"),
        ("丽江古城", "lijiang ancient town old street"),
        ("平遥古城墙", "pingyao ancient city wall"),
        ("凤凰古城", "fenghuang ancient town riverside"),
        ("宏村月沼", "hongcun village pond reflection"),
        ("香格里拉草原", "shangri-la grassland plateau"),
        ("稻城雪山", "daocheng yading snow peak"),
        ("青海湖畔", "qinghai lake shoreline"),
        ("泸沽湖", "lugu lake wooden boats"),
        ("婺源花海", "wuyuan village rapeseed flowers"),
    ],
    "科技类": [
        ("芯片晶圆", "semiconductor wafer chip macro"),
        ("数据中心", "data center server room"),
        ("机器人手臂", "robotic arm factory automation"),
        ("量子实验室", "quantum computer laboratory"),
        ("无人机编队", "drone fleet formation sky"),
        ("自动驾驶", "autonomous car lidar sensor"),
        ("太空望远镜", "space telescope observatory"),
        ("火星探测车", "mars rover planet surface"),
        ("卫星发射塔", "satellite launch tower"),
        ("生物实验室", "biotech laboratory microscope"),
        ("虚拟现实", "virtual reality headset user"),
        ("人工智能大脑", "artificial intelligence neural network"),
        ("服务器机房", "server racks cloud computing"),
        ("芯片制造", "chip manufacturing clean room"),
        ("电动车充电", "electric vehicle charging station"),
        ("风力发电", "wind turbine farm renewable"),
        ("太阳能电站", "solar panel farm desert"),
        ("核聚变装置", "fusion reactor tokamak"),
        ("深海潜水器", "deep sea submarine research"),
        ("极地科考站", "polar research station arctic"),
    ],
}


def load_topics():
    if os.path.exists(TOPICS_JSON):
        try:
            data = json.load(open(TOPICS_JSON, encoding="utf-8"))
            if isinstance(data, list):
                return data
        except Exception as e:
            print(f"! 读取 topics.json 失败: {e}", file=sys.stderr)
    return []


def save_topics(data):
    tmp = TOPICS_JSON + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, TOPICS_JSON)


def main():
    ap = argparse.ArgumentParser(description="每3天补充一批话题（风景/名人/事件/景点/科技）")
    ap.add_argument("--per-category", type=int, default=6, help="每类抽取数量（默认6）")
    ap.add_argument("--dry-run", action="store_true", help="只打印不写入")
    args = ap.parse_args()

    existing = load_topics()
    existing_cn = {d["cn"] for d in existing}

    added = []
    for cat, pool in CANDIDATES.items():
        fresh = [p for p in pool if p[0] not in existing_cn]
        random.shuffle(fresh)
        picked = fresh[:args.per_category]
        for cn, en in picked:
            existing.append({"cn": cn, "en": en})
            existing_cn.add(cn)
            added.append({"cat": cat, "cn": cn, "en": en})
        if not picked:
            print(f"! {cat}: 候选已全部用完，无新增", file=sys.stderr)

    summary = {
        "added_total": len(added),
        "added": added,
        "topics_total_before": len(existing) - len(added),
        "topics_total_after": len(existing),
    }

    if args.dry_run:
        print(json.dumps({"dry_run": True, **summary}, ensure_ascii=False, indent=2))
        return

    if added:
        # 备份
        if os.path.exists(TOPICS_JSON):
            bak = TOPICS_JSON + ".bak-" + datetime.now().strftime("%Y%m%d%H%M%S")
            shutil.copy(TOPICS_JSON, bak)
        save_topics(existing)

    print(json.dumps({"status": "success", **summary}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
