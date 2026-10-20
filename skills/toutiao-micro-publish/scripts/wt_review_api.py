#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""微头条发布前终审（API 版，2026-10-20）

背景：原来走 ds_web_review.py（无头 Chrome 登录 chat.deepseek.com），登录态一掉
整个流水线就“停发”。现在改用主模型 API（opencode-go / deepseek-v4.1-flash），
提示词与网页版保持一致（直接复用 ds_web_review.PROMPT_TMPL），不再依赖浏览器登录。

用法:
  python3 wt_review_api.py <draft.txt> [--out /tmp/ds_verdict.md] [--json]

输出:
  JSON {"ok": true, "verdict": "PASS|FIX|UNKNOWN", "model": "...", "answer_chars": N}
  失败 JSON {"ok": false, "error": "..."}
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from wt_common import llm, load_ledger_recent_text  # noqa: E402
from ds_web_review import PROMPT_TMPL  # noqa: E402


def build_prompt(draft, recent):
    return PROMPT_TMPL.replace("{draft}", draft).replace("{recent}", recent or "（无）")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("draft")
    ap.add_argument("--out", default="/tmp/ds_verdict.md")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    draft = open(args.draft, encoding="utf-8").read().strip()
    if not draft:
        print(json.dumps({"ok": False, "error": "草稿为空"}, ensure_ascii=False))
        return 0

    prompt = build_prompt(draft, load_ledger_recent_text(6))
    try:
        answer, model = llm(prompt, max_tokens=12000, temperature=0.2)
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"}, ensure_ascii=False))
        return 0

    with open(args.out, "w", encoding="utf-8") as f:
        f.write(answer)
    m = re.findall(r"VERDICT\s*[:：]\s*(PASS|FIX)", answer, re.I)
    verdict = m[-1].upper() if m else "UNKNOWN"
    print(json.dumps({"ok": True, "verdict": verdict, "model": model,
                      "answer_chars": len(answer)}, ensure_ascii=False))
    if not args.json:
        print("\n--- 终审结果 ---")
        print(answer[:4000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
