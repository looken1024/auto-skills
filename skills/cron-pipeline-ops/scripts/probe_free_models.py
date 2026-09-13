#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""免费模型探活：判断候选模型“能不能用/能不能当 cron 大脑”。

为什么要两档：
  小请求 → 只看模型是否活着；
  几千字输入 → 看输入 token 配额是否吃得下（cron 长会话起步 6 万+ token，
  某些模型（如 gemma-4-26b:free）上游 input_token_count 上限只有 16000/分钟，
  小请求 200 OK、真实会话必 429。）

坑：max_tokens 给太小（如 20），推理型模型可能只产出 reasoning、返回
  {"error":"empty response content"} —— 那是**假阴性**，不是模型不可用。
  本脚本统一用 300。

用法：
  python3 probe_free_models.py            # 用内置候选清单
  python3 probe_free_models.py m1 m2 ...   # 指定模型

依赖：requests；key 从 ~/.hermes/.env 的 CUSTOM_CLINE_API_KEY / CUSTOM_CLINE_2_API_KEY 读；
      走本地解包代理（cline_local provider）http://127.0.0.1:8899/v1。
"""
import os
import re
import sys
import time

import requests

BASE = os.environ.get("CLINE_LOCAL_BASE", "http://127.0.0.1:8899/v1")
ENV = os.path.expanduser("~/.hermes/.env")

DEFAULT_MODELS = [
    "dots-studio/dots-3-note-preview:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "google/gemma-4-31b-it:free",
    "google/gemma-4-26b-a4b-it:free",
    "cohere/north-mini-code:free",
]

# ~3000 字输入：用于暴露“输入配额太小”的模型
LONG_INPUT = "这是一段用于测试长上下文输入配额的文本。" * 160


def load_key():
    env = dict(re.findall(r"^(\w+)=(.*)$", open(ENV, encoding="utf-8").read(), re.M))
    return env.get("CUSTOM_CLINE_API_KEY") or env.get("CUSTOM_CLINE_2_API_KEY")


def probe(key, model, prompt, tag, max_tokens=300):
    t0 = time.time()
    try:
        r = requests.post(
            f"{BASE}/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": model, "messages": [{"role": "user", "content": prompt}],
                  "max_tokens": max_tokens, "stream": False},
            timeout=120,
        )
        dt = time.time() - t0
        if r.status_code == 200:
            d = r.json()
            c = (d.get("choices") or [{}])[0]
            txt = ((c.get("message") or {}).get("content") or "").strip()
            print(f"{model:48s} [{tag}] 200 {dt:5.1f}s len={len(txt):4d} -> {txt[:40]!r}")
            return True
        body = r.text[:160].replace("\n", " ")
        print(f"{model:48s} [{tag}] {r.status_code} {dt:5.1f}s -> {body}")
        return False
    except Exception as e:  # 网络/超时
        print(f"{model:48s} [{tag}] ERR {time.time()-t0:5.1f}s {type(e).__name__}: {str(e)[:70]}")
        return False


def main():
    models = sys.argv[1:] or DEFAULT_MODELS
    key = load_key()
    if not key:
        print("没在 ~/.hermes/.env 找到 CUSTOM_CLINE_API_KEY，无法探活")
        raise SystemExit(1)
    print(f"探活端点 {BASE}（本地解包代理）\n")
    for m in models:
        ok_short = probe(key, m, "回复两个字：可用", "小请求")
        if ok_short:
            probe(key, m, LONG_INPUT + "\n\n上面这段文本重复了多少次？只回数字。", "长输入≈3k字")
        print()
    print("读法：小请求 200 + 长输入 429/500 且带 input_token_count limit → 不能当 cron 大脑；"
          "两档都 200 → 可用，但仍需跑一次“4 步探测”确认多步工具能力。")


if __name__ == "__main__":
    main()
