#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用 DeepSeek 网页版（chat.deepseek.com）做发布前终审复核。

背景：本站已用无头 Chrome（--remote-debugging-port=9222）登录过 chat.deepseek.com。
本脚本直接通过 CDP 驱动那个浏览器：新建对话 → 贴入"待发稿 + 复核清单" → 等回答 →
抓取回答并解析 VERDICT: PASS / FIX。

用法：
  python3 ds_web_review.py <draft.txt> [--recent recent_endings.txt] [--timeout 420] [--json]

输出（stdout）：
  JSON: {"ok":true,"verdict":"PASS|FIX|UNKNOWN","answer_file":"...","answer_chars":N}
  失败: {"ok":false,"error":"..."}   （退出码 2）

依赖：系统 python3 + websocket-client（已装）。Chrome 需在 9222 端口运行。
"""
import argparse
import json
import os
import re
import sys
import time

import websocket  # websocket-client

CHROME = "http://127.0.0.1:9222"
URL = "https://chat.deepseek.com/"


def ws_url():
    """复用已有的 deepseek 标签；没有就新建一个（绝不复用头条/公众号的标签，避免打架）"""
    import urllib.request
    with urllib.request.urlopen(CHROME + "/json/list", timeout=5) as r:
        tabs = json.load(r)
    pages = [t for t in tabs if t.get("type") == "page"]
    if not pages:
        raise RuntimeError("没有可用标签页（Chrome 是否在 9222 上运行？）")
    for t in pages:
        if "deepseek.com" in (t.get("url") or ""):
            return t["webSocketDebuggerUrl"], t["id"]
    # 新建标签（Chrome 新版要求 PUT，老版 GET）
    for method in ("PUT", "GET"):
        try:
            req = urllib.request.Request(CHROME + "/json/new?url=about:blank", method=method)
            with urllib.request.urlopen(req, timeout=8) as r:
                t = json.load(r)
            return t["webSocketDebuggerUrl"], t["id"]
        except Exception:
            continue
    raise RuntimeError("无法新建标签页")


class CDP:
    def __init__(self, url):
        try:
            self.ws = websocket.create_connection(url, timeout=60, max_size=64 * 1024 * 1024,
                                                  suppress_origin=True)
        except Exception:
            # 某些 Chrome 版本要求带 origin，试一下
            self.ws = websocket.create_connection(url, timeout=60, max_size=64 * 1024 * 1024,
                                                  origin="http://127.0.0.1:9222")
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
        r = self.send("Runtime.evaluate", expression=expr, returnByValue=True, awaitPromise=True,
                      timeout=timeout_ms)
        return (r.get("result") or {}).get("value")

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass


PROMPT_TMPL = """你是今日头条微头条账号「棱镜折射」的**发布前终审**。请对下面这条待发内容做严格复核，只挑问题，不要夸奖、不要复述我的要求。

【待发内容】
{draft}

【最近已发内容（防止结尾/选题撞车）】
{recent}

【复核清单】
1) 事实核查：把文中的每个数字、人名、机构、时间、人物引语逐一挑出来判断能否站得住；凡是你不能确认的，直接标"未证实"，并给出更稳的替代表述。
2) 夸大与绝对化：有没有"纯粹/全部/一倍/唯一"这类过头说法。
3) 合规风险：是否会构成不实信息、侵犯名誉、消费悲剧。
4) 观点与论据是否自相矛盾（论据方向有没有反了）。
5) 结尾：是否与上面"最近已发内容"的结尾重复；句式是否又是同一模板。
6) 事实来源标注：关键数据有没有交代出处。

【输出格式（必须严格遵守，最后两行按此写）】
问题清单：逐条列（原文片段 → 问题 → 建议改法）；没问题的项写"无"
必改项：只列发布前必须改的（没有就写"无"）
VERDICT: PASS
或
VERDICT: FIX
"""


def build_prompt(draft, recent):
    return PROMPT_TMPL.replace("{draft}", draft).replace("{recent}", recent or "（无）")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("draft")
    ap.add_argument("--recent", default=None, help="最近已发内容文件（标题/结尾），用于查重")
    ap.add_argument("--timeout", type=int, default=420, help="等待回答的最长秒数")
    ap.add_argument("--out", default="/tmp/ds_web_review_answer.md")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    draft = open(a.draft, encoding="utf-8").read().strip()
    if a.recent and os.path.exists(a.recent):
        recent = open(a.recent, encoding="utf-8").read().strip()
    else:
        # 默认自动取台账最近 5 条（标题+首句）用于查重
        led = os.path.expanduser("~/.hermes/skills/toutiao-micro-publish/logs/published.log")
        try:
            lines = [l.strip() for l in open(led, encoding="utf-8")
                     if l.strip() and not l.startswith("#")]
            recent = "\n".join(lines[-5:])
        except FileNotFoundError:
            recent = ""
    prompt = build_prompt(draft, recent)

    try:
        url, tid = ws_url()
        cdp = CDP(url)
        cdp.send("Page.enable")
        cdp.send("Runtime.enable")
        # 关键：headless 后台标签会被“节流”，DeepSeek 的消息可能迟迟不落到 DOM。
        # 打开焦点模拟 + 把标签提到前面，并在轮询时强制重绘（截图）。
        try:
            cdp.send("Emulation.setFocusEmulationEnabled", enabled=True)
        except Exception:
            pass
        try:
            cdp.send("Page.bringToFront")
        except Exception:
            pass
        # 打开新对话
        cdp.send("Page.navigate", url=URL)
        time.sleep(6)
        for _ in range(15):
            if cdp.js("document.querySelector('textarea') ? 1 : 0") == 1:
                break
            time.sleep(2)
        if "/sign_in" in (cdp.js("location.href") or ""):
            raise RuntimeError("DeepSeek 未登录（跳到 sign_in），需要重新扫码/验证码登录")
        if cdp.js("document.querySelector('textarea') ? 1 : 0") != 1:
            raise RuntimeError("找不到输入框（页面可能改版或未加载完）")

        # 清空并贴入 prompt
        cdp.js("(() => { const t=document.querySelector('textarea'); t.focus(); t.select(); return 1; })()")
        time.sleep(0.4)
        cdp.send("Input.dispatchKeyEvent", type="keyDown", key="Backspace", code="Backspace",
                 windowsVirtualKeyCode=8, nativeVirtualKeyCode=8)
        cdp.send("Input.dispatchKeyEvent", type="keyUp", key="Backspace", code="Backspace",
                 windowsVirtualKeyCode=8, nativeVirtualKeyCode=8)
        for i in range(0, len(prompt), 700):
            cdp.send("Input.insertText", text=prompt[i:i + 700])
            time.sleep(0.35)
        filled = cdp.js("document.querySelector('textarea') ? document.querySelector('textarea').value.length : 0")
        if not filled or filled < len(prompt) * 0.9:
            raise RuntimeError(f"输入框内容不完整（{filled}/{len(prompt)}）")

        # 发送
        cdp.send("Input.dispatchKeyEvent", type="keyDown", key="Enter", code="Enter",
                 windowsVirtualKeyCode=13, nativeVirtualKeyCode=13)
        cdp.send("Input.dispatchKeyEvent", type="keyUp", key="Enter", code="Enter",
                 windowsVirtualKeyCode=13, nativeVirtualKeyCode=13)

        # 等待回答：取“含最终 VERDICT 行 且不含【待发内容】标记”的最小容器（后者只出现在提问里）
        extract = ("(() => { const all=[...document.querySelectorAll('div,section,article')];"
                   "const ok=all.filter(e=>{const t=e.innerText||'';"
                   "const has=(t.includes('VERDICT: PASS')||t.includes('VERDICT: FIX')||"
                   "t.includes('VERDICT：PASS')||t.includes('VERDICT：FIX'));"
                   "return has && !t.includes('\u3010\u5f85\u53d1\u5185\u5bb9\u3011');});"
                   "if(!ok.length) return '';"
                   "ok.sort((a,b)=>(a.innerText.length-b.innerText.length));"
                   "return ok[0].innerText; })()")
        deadline = time.time() + a.timeout
        last, stable = "", 0
        while time.time() < deadline:
            time.sleep(10)
            # 强制重绘：headless 下页面不重绘时内容可能不落 DOM
            try:
                cdp.send("Page.captureScreenshot", format="jpeg", quality=20)
            except Exception:
                pass
            txt = cdp.js(extract) or ""
            if len(txt) == len(last) and len(txt) > 150:
                stable += 1
                if stable >= 3:
                    break
            else:
                stable = 0
            last = txt
        answer = cdp.js(extract) or last
        cdp.close()
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"}, ensure_ascii=False))
        sys.exit(2)

    open(a.out, "w", encoding="utf-8").write(answer)
    m = re.findall(r"VERDICT\s*[:：]\s*(PASS|FIX)", answer, re.I)
    verdict = (m[-1].upper() if m else "UNKNOWN")
    res = {"ok": True, "verdict": verdict, "answer_file": a.out, "answer_chars": len(answer)}
    print(json.dumps(res, ensure_ascii=False))
    if not a.json:
        print("\n--- DeepSeek 网页版复审核结果 ---")
        print(answer[:4000])


if __name__ == "__main__":
    main()
