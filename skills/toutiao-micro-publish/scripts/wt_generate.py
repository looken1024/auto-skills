#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""微头条脚本化生成：选题（小上下文 LLM）→ 写稿（小上下文 LLM）→ 落盘。

每次模型调用都是独立小请求（2-6k 字符），不走 agent 长会话，绕开免费池的输入 token 限流。
用法：
  python3 wt_generate.py                 # 从 /tmp/wt_hot.json 选题目并写稿
  python3 wt_generate.py --topic "xxx"   # 指定题目直接写稿
输出：/tmp/wt_topic.json + /tmp/wt_draft.txt（stdout 打印两者）
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wt_common import llm, load_ledger_titles, load_ledger_recent_text  # noqa: E402

STYLE = """写作硬要求（今日头条微头条，账号「棱镜折射」）：
- 400-500 字，中文，一段一句话为主，短句，口语化，读起来像人在说话
- 一篇只讲一个核心观点，不要面面俱到
- 有情绪、可以带一点反讽，可以有方言口吻（比如"咱""啥""咋"），但不要油腻
- 数字要具体（金额、天数、比例、时间都写清楚）
- 结尾抛一个问题，或给一条能马上用的建议
- 严禁 AI 惯用语："近日""随着…""值得注意的是""这一事件""不难看出""总而言之""本质上"
- 严禁网感梗句："离谱在哪""谁懂啊""绝了""破防了""CPU 烧了"
- 不要 markdown 标记、不要小标题、不要列表、不要 emoji，纯自然段
- 直接输出正文，不要写"标题："、不要解释、不要加引号包裹整篇"""


def pick_topic(hot, recent):
    hotlist = "\n".join(f"{i}. {h['title']}" for i, h in enumerate(hot, 1))
    prompt = f"""你是今日头条微头条账号「棱镜折射」的选题编辑。下面有两块信息。

【今天的热榜】
{hotlist}

【我们最近已经发过的（不能重复选题/重复角度）】
{recent or '（无）'}

从热榜里选 1 个最适合微头条的题目。选择优先级：民生利益（钱、假期、物价、养老、医疗、消费坑）> 职场/教育 > 生活常识 > 社会情绪。
必须避开：与上面已发内容同主题或同角度的；政治、刑案、悲剧、明星八卦、体育赛事比分、纯国际新闻。

只输出 JSON，不要别的：
{{"topic": "选中的题目（照抄热榜原句）", "angle": "我们打算切的角度，一句话", "core_view": "核心观点，一句话", "known_facts": ["写稿时必须用到的已知事实/数字，没把握的不要写"], "rejected": "为什么没选其它题目，一句话"}}"""
    txt, model = llm(prompt, max_tokens=900, temperature=0.4)
    m = re.search(r"\{.*\}", txt, re.S)
    if not m:
        raise RuntimeError(f"选题模型没返回 JSON：{txt[:200]}")
    data = json.loads(m.group(0))
    data["_model"] = model
    return data


def write_draft(topic_info, recent):
    prompt = f"""给今日头条微头条账号「棱镜折射」写一条微头条。

【题目】{topic_info['topic']}
【切入角度】{topic_info.get('angle','')}
【核心观点】{topic_info.get('core_view','')}
【可用事实（只用这些，没把握的一律不要写）】{'；'.join(topic_info.get('known_facts') or []) or '（无，只能用常识性表述，不要编具体数字）'}

【最近发过的（避免结尾句式和内容撞车）】
{recent or '（无）'}

{STYLE}

现在直接写正文。"""
    txt, model = llm(prompt, max_tokens=1600, temperature=0.85)
    txt = txt.strip().strip('"').strip()
    # 去掉可能出现的标题行
    txt = re.sub(r"^(标题|题目)[:：].*\n+", "", txt)
    return txt, model


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hot", default="/tmp/wt_hot.json")
    ap.add_argument("--topic", default=None, help="跳过选题，直接写这个题目")
    ap.add_argument("--topic-file", default=None, help="读 /tmp/wt_topic.json 里的选题信息来写稿")
    ap.add_argument("--facts", default="/tmp/wt_facts.json", help="事实清单文件（wt_facts.py 产出）")
    ap.add_argument("--stage", default="all", choices=["all", "pick", "write"],
                    help="pick=只选题；write=只写稿；all=选题+写稿")
    ap.add_argument("--out-draft", default="/tmp/wt_draft.txt")
    ap.add_argument("--out-topic", default="/tmp/wt_topic.json")
    a = ap.parse_args()

    recent = load_ledger_recent_text(6)

    if a.stage == "pick":
        hot = json.load(open(a.hot, encoding="utf-8"))
        if not hot:
            raise RuntimeError(f"{a.hot} 里没有热榜数据，先跑 wt_hotlist.py")
        topic_info = pick_topic(hot, recent)
        print(f"[gen] 选题模型：{topic_info.get('_model')}", file=sys.stderr)
        print(f"[gen] 选中：{topic_info['topic']} —— {topic_info.get('angle','')}", file=sys.stderr)
        print(f"[gen] 排除理由：{topic_info.get('rejected','')}", file=sys.stderr)
        json.dump(topic_info, open(a.out_topic, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(json.dumps(topic_info, ensure_ascii=False, indent=1))
        return

    if a.topic_file and os.path.exists(a.topic_file):
        topic_info = json.load(open(a.topic_file, encoding="utf-8"))
    elif a.topic:
        topic_info = {"topic": a.topic, "angle": "", "core_view": "", "known_facts": [], "_model": "skip"}
    else:
        hot = json.load(open(a.hot, encoding="utf-8"))
        if not hot:
            raise RuntimeError(f"{a.hot} 里没有热榜数据，先跑 wt_hotlist.py")
        topic_info = pick_topic(hot, recent)
        print(f"[gen] 选题模型：{topic_info.get('_model')}", file=sys.stderr)
        print(f"[gen] 选中：{topic_info['topic']} —— {topic_info.get('angle','')}", file=sys.stderr)
        print(f"[gen] 排除理由：{topic_info.get('rejected','')}", file=sys.stderr)

    # 合并 wt_facts.py 抓到的已核实事实
    if os.path.exists(a.facts):
        try:
            fx = json.load(open(a.facts, encoding="utf-8"))
            extra = fx.get("facts") or []
            if extra:
                topic_info["known_facts"] = extra + list(topic_info.get("known_facts") or [])
                topic_info["sources"] = fx.get("sources") or []
                print(f"[gen] 已并入 {len(extra)} 条外部核实事实", file=sys.stderr)
        except Exception as e:
            print(f"[gen] 事实文件读取失败（忽略）：{e}", file=sys.stderr)

    draft, model = write_draft(topic_info, recent)
    topic_info["_write_model"] = model
    topic_info["chars"] = len(re.sub(r"\s", "", draft))
    json.dump(topic_info, open(a.out_topic, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    open(a.out_draft, "w", encoding="utf-8").write(draft + "\n")

    print(f"\n===== 选题 =====")
    print(topic_info["topic"])
    print(f"===== 正文（{topic_info['chars']} 字，模型 {model}）=====")
    print(draft)
    if not (380 <= topic_info["chars"] <= 560):
        print(f"\n[gen][警告] 字数 {topic_info['chars']} 偏离 400-500 区间，需要重写或调整", file=sys.stderr)


if __name__ == "__main__":
    main()
