#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按复审意见改稿（小上下文 LLM）：输入原稿 + 复审文本，输出改后正文。

用法：python3 wt_revise.py --draft /tmp/wt_draft.txt --review /tmp/ds_verdict.md [--out /tmp/wt_draft.txt]
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wt_common import llm, load_ledger_recent_text  # noqa: E402

STYLE = """改写硬要求：
- 仍然 400-500 字，中文短句、口语化、一篇一个观点，结尾抛问题或给建议
- 禁 AI 惯用语（近日/随着/值得注意的是/这一事件/本质上）与网感梗句（离谱在哪/谁懂啊/绝了）
- 不要 markdown、不要小标题、不要 emoji、纯自然段
- 只输出改后的正文，不要解释、不要加标题、不要引号包裹"""


def extract_must_fix(review):
    """从复审文本里取「必改项」段；取不到就整段喂进去"""
    m = re.search(r"必改项[^\n]*\n(.*?)(?:\n\s*(?:VERDICT|【|问题清单|结论)|\Z)", review, re.S)
    seg = m.group(1).strip() if m else ""
    if len(seg) < 10:
        seg = review[:2500]
    return seg[:2500]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--draft", required=True)
    ap.add_argument("--review", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--note", default="", help="额外要求（例如 'DeepSeek 指出的论据方向问题'）")
    a = ap.parse_args()

    draft = open(a.draft, encoding="utf-8").read().strip()
    review = open(a.review, encoding="utf-8").read()
    must = extract_must_fix(review)
    recent = load_ledger_recent_text(6)

    prompt = f"""下面是待发布的微头条正文，以及复审给出的必须修改项。请按必改项逐条改好，其它地方尽量保留。

【原文】
{draft}

【必须修改项】
{must}

{a.note}

【最近发过的（结尾不要和它们撞句式）】
{recent or '（无）'}

{STYLE}"""
    new, model = llm(prompt, max_tokens=1800, temperature=0.7)
    new = new.strip().strip('"').strip()
    new = re.sub(r"^(标题|题目)[:：].*\n+", "", new)
    chars = len(re.sub(r"\s", "", new))
    out = a.out or a.draft
    open(out, "w", encoding="utf-8").write(new + "\n")
    print(json.dumps({"ok": True, "model": model, "chars": chars, "written": out,
                      "first_line": new.splitlines()[0][:50]}, ensure_ascii=False))
    if not (380 <= chars <= 560):
        print(f"[revise][警告] 改后字数 {chars} 偏离区间", file=sys.stderr)


if __name__ == "__main__":
    main()
