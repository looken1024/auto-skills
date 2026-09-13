#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""微头条流水线公共件：小上下文 LLM 调用（绕开限流）+ CDP 标签管理 + 台账 + 邮件告警。

设计要点（2026-09-13 新增，为「脚本化绕开限流」服务）：
- **每次模型调用都是独立小请求**（prompt 控制在 2-6k 字符），不走 agent 长会话，
  于是免费池里 gemma-4-26b(16k 输入/分钟上限) 也能用；长会话必然 429。
- 模型按序尝试，失败自动换下一个；全部失败才报错。
- 走本地解包代理 http://127.0.0.1:8899（cline-unwrap-proxy），端点与 agent 一致。
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

import requests

PROXY = "http://127.0.0.1:8899/v1/chat/completions"
CHROME = "http://127.0.0.1:9222"
SKILL = os.path.expanduser("~/.hermes/skills/toutiao-micro-publish")
LEDGER = os.path.join(SKILL, "logs", "published.log")

# 小上下文优先用 gemma-26b（快、中文好），限流了再往后排
MODEL_CHAIN = [
    "google/gemma-4-26b-a4b-it:free",
    "dots-studio/dots-3-note-preview:free",
    "cohere/north-mini-code:free",
    "google/gemma-4-31b-it:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
]


def _api_key():
    txt = open(os.path.expanduser("~/.hermes/.env"), encoding="utf-8").read()
    m = re.search(r"^CUSTOM_CLINE_API_KEY=(.+)$", txt, re.M)
    if not m:
        raise RuntimeError("找不到 CUSTOM_CLINE_API_KEY")
    return m.group(1).strip()


def llm(prompt, system=None, max_tokens=2000, temperature=0.8, models=None, timeout=180, verbose=True):
    """小上下文单次调用。返回 (text, model_used)；全部失败抛 RuntimeError。"""
    key = _api_key()
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": prompt})
    errs = []
    for m in (models or MODEL_CHAIN):
        try:
            t0 = time.time()
            r = requests.post(PROXY, headers={"Authorization": f"Bearer {key}",
                                              "Content-Type": "application/json"},
                              json={"model": m, "messages": msgs, "max_tokens": max_tokens,
                                    "temperature": temperature, "stream": False},
                              timeout=timeout)
            dt = time.time() - t0
            if r.status_code != 200:
                errs.append(f"{m}: HTTP {r.status_code} {r.text[:80]}")
                if verbose:
                    print(f"   [llm] {m} 失败 HTTP {r.status_code}", file=sys.stderr)
                continue
            d = r.json()
            txt = ((d.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
            if not txt.strip():
                errs.append(f"{m}: 空回复")
                if verbose:
                    print(f"   [llm] {m} 空回复", file=sys.stderr)
                continue
            if verbose:
                print(f"   [llm] {m} OK {dt:.1f}s ({len(prompt)} 字符入 / {len(txt)} 出)", file=sys.stderr)
            return txt.strip(), m
        except Exception as e:
            errs.append(f"{m}: {type(e).__name__} {str(e)[:70]}")
            if verbose:
                print(f"   [llm] {m} 异常 {type(e).__name__}", file=sys.stderr)
    raise RuntimeError("所有免费模型都不可用：" + " | ".join(errs[:5]))


# ---------------- CDP ----------------
def _http_json(url, method="GET"):
    req = urllib.request.Request(url, method=method)
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.load(r)


def cdp_tab(prefer_host=None, new_url="about:blank"):
    """复用已有标签（按域名匹配），没有就新建。返回 (CDP, tab_id)。"""
    import websocket
    tabs = _http_json(CHROME + "/json/list")
    pages = [t for t in tabs if t.get("type") == "page"]
    if not pages:
        raise RuntimeError("Chrome 没在 9222 上跑？")
    target = None
    if prefer_host:
        for t in pages:
            if prefer_host in (t.get("url") or ""):
                target = t
                break
    if target is None:
        last = None
        for method in ("PUT", "GET"):
            try:
                target = _http_json(f"{CHROME}/json/new?url={new_url}", method=method)
                break
            except Exception as e:
                last = e
        if target is None:
            raise RuntimeError(f"无法新建标签页：{last}")
    for attempt in range(2):
        try:
            ws = websocket.create_connection(target["webSocketDebuggerUrl"], timeout=60,
                                             max_size=64 * 1024 * 1024, suppress_origin=True)
            break
        except Exception:
            if attempt:
                raise
            time.sleep(1)
    return CDP(ws), target.get("id")


class CDP:
    def __init__(self, ws):
        self.ws = ws
        self.i = 0

    def send(self, method, **params):
        self.i += 1
        self.ws.send(json.dumps({"id": self.i, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == self.i:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})

    def js(self, expr, timeout_ms=30000):
        r = self.send("Runtime.evaluate", expression=expr, returnByValue=True,
                      awaitPromise=True, timeout=timeout_ms)
        return (r.get("result") or {}).get("value")

    def goto(self, url, wait=4.0):
        self.send("Page.enable")
        self.send("Page.navigate", url=url)
        time.sleep(wait)

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass


# ---------------- 台账 ----------------
def load_ledger_titles(n=60):
    if not os.path.exists(LEDGER):
        return []
    out = []
    for line in open(LEDGER, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        out.append(parts[1] if len(parts) > 1 else line[:40])
    return out[-n:]


def load_ledger_recent_text(n=6):
    """最近若干条的完整台账行（含首句），给查重/风格对齐用"""
    if not os.path.exists(LEDGER):
        return ""
    lines = [l.strip() for l in open(LEDGER, encoding="utf-8") if l.strip() and not l.startswith("#")]
    return "\n".join(lines[-n:])


def append_ledger(topic, status, first_sentence):
    os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
    stamp = time.strftime("%Y-%m-%d %H:%M")
    with open(LEDGER, "a", encoding="utf-8") as f:
        f.write(f"{stamp} | {topic} | {status} | {first_sentence}\n")


def notify_email(subject, body):
    try:
        script = os.path.join(SKILL, "scripts", "notify_email.py")
        subprocess.run([sys.executable, script, subject, body], timeout=90,
                       capture_output=True, text=True)
        return True
    except Exception:
        return False
