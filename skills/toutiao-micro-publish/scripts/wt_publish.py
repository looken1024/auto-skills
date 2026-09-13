#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""微头条发布（纯脚本 CDP，不经 agent）：清空编辑器 → 分段填入 → 回读校验 → 点一次发布 → 验证 → 写台账。

用法：
  python3 wt_publish.py /tmp/wt_draft.txt [--dry-run] [--topic "关键词"] [--json]

安全设计：
- 发布前先查台账（同主题/同关键词已发则拒绝）
- 清空编辑器用 Ctrl+A + Backspace（草稿页残留会导致发重）
- 只点一次"发布"；点击后校验 URL 与列表首条
- 任何失败都返回 ok=false + error，由上层发邮件
"""
import argparse
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wt_common import cdp_tab, load_ledger_titles, append_ledger, notify_email  # noqa: E402

PUBLISH_URL = "https://mp.toutiao.com/profile_v4/weitoutiao/publish"
LIST_URL = "https://mp.toutiao.com/profile_v4/weitoutiao"

CLEAR_JS = """(() => {
  const ed = document.querySelector('.ProseMirror[contenteditable="true"]') || document.querySelector('.ProseMirror');
  if (!ed) return 'NO_EDITOR';
  ed.focus();
  const sel = window.getSelection(); const r = document.createRange();
  r.selectNodeContents(ed); sel.removeAllRanges(); sel.addRange(r);
  return 'FOCUSED';
})()"""

READ_JS = """(() => {
  const ed = document.querySelector('.ProseMirror[contenteditable="true"]') || document.querySelector('.ProseMirror');
  let t = '';
  if (ed) {
    // 关键：占位符是 ProseMirror widget（.syl-placeholder / ignoreel="true"），不算正文
    const c = ed.cloneNode(true);
    c.querySelectorAll('.syl-placeholder, [ignoreel="true"]').forEach(n => n.remove());
    t = c.innerText || c.textContent || '';
  }
  const body = document.body.innerText || '';
  const m = body.match(/正文字数[:：]?\\s*(\\d+)/);
  return JSON.stringify({text: t, count: m ? m[1] : null});
})()"""


def count_displayed(cdp):
    try:
        out = cdp.js(READ_JS)
        return json.loads(out or "{}")
    except Exception:
        return {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("draft")
    ap.add_argument("--topic", default="", help="台账里的主题关键词（用于查重与台账写入）")
    ap.add_argument("--dry-run", action="store_true", help="只填不发布")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    draft = open(a.draft, encoding="utf-8").read().strip()
    paras = [p.strip() for p in re.split(r"\n+", draft) if p.strip()]
    plain = re.sub(r"\s", "", draft)

    def fail(msg, **extra):
        res = {"ok": False, "error": msg, "chars": len(plain)}
        res.update(extra)
        print(json.dumps(res, ensure_ascii=False))
        sys.exit(2)

    # 1) 台账查重
    titles = load_ledger_titles(80)
    key = a.topic or (paras[0][:14] if paras else "")
    for t in titles:
        if key and (key in t or (len(key) > 5 and t[:6] in key)):
            fail(f"台账里已有同主题记录，拒绝发布：{t}")

    # 2) 打开发布页（**自己新建标签**，绝不复用别的标签，避免互相踩）
    cdp, _ = cdp_tab(prefer_host=None, new_url=PUBLISH_URL)
    cdp.send("Page.enable")
    cdp.send("Runtime.enable")
    cdp.goto(PUBLISH_URL, wait=6)
    time.sleep(2)
    url = cdp.js("location.href") or ""
    if "login" in url or "sso" in url:
        cdp.close()
        fail(f"未登录（跳到 {url}），需要重新注入 cookie")
    if cdp.js("document.querySelector('.ProseMirror') ? 1 : 0") != 1:
        # 再等一会儿
        for _ in range(10):
            time.sleep(2)
            if cdp.js("document.querySelector('.ProseMirror') ? 1 : 0") == 1:
                break
        else:
            cdp.close()
            fail("找不到编辑器（.ProseMirror），页面可能未加载完或改版")

    # 3) 清空 + 填入
    st = cdp.js(CLEAR_JS)
    if st != "FOCUSED":
        cdp.close()
        fail(f"聚焦编辑器失败：{st}")
    time.sleep(0.3)
    cdp.send("Input.dispatchKeyEvent", type="keyDown", key="Backspace", code="Backspace",
             windowsVirtualKeyCode=8, nativeVirtualKeyCode=8)
    cdp.send("Input.dispatchKeyEvent", type="keyUp", key="Backspace", code="Backspace",
             windowsVirtualKeyCode=8, nativeVirtualKeyCode=8)
    time.sleep(0.3)
    residual = count_displayed(cdp).get("text") or ""
    if len(re.sub(r"\s", "", residual)) > 5:
        cdp.close()
        fail(f"编辑器没清干净，残留 {len(residual)} 字符，拒绝继续（防发重）")

    for i, p in enumerate(paras):
        if i:
            cdp.send("Input.dispatchKeyEvent", type="keyDown", key="Enter", code="Enter",
                     windowsVirtualKeyCode=13, nativeVirtualKeyCode=13)
            cdp.send("Input.dispatchKeyEvent", type="keyUp", key="Enter", code="Enter",
                     windowsVirtualKeyCode=13, nativeVirtualKeyCode=13)
            time.sleep(0.15)
        cdp.send("Input.insertText", text=p)
        time.sleep(0.25)

    time.sleep(1.5)
    got = count_displayed(cdp)
    filled = re.sub(r"\s", "", got.get("text") or "")
    if len(filled) < len(plain) * 0.9:
        cdp.close()
        fail(f"回读字数不符：页面 {len(filled)} / 期望 {len(plain)}")
    print(f"[pub] 已填入 {len(filled)} 字（页面计数 {got.get('count')}）", file=sys.stderr)

    if a.dry_run:
        cdp.close()
        print(json.dumps({"ok": True, "dry_run": True, "chars": len(filled),
                          "count": got.get("count")}, ensure_ascii=False))
        return

    # 4) 点一次发布
    click_js = ("(() => { const bs=[...document.querySelectorAll('button')];"
                "const b=bs.find(x=>x.innerText.trim()==='发布' && !x.disabled);"
                "if(!b) return 'NO_BUTTON'; b.click(); return 'CLICKED'; })()")
    st = cdp.js(click_js)
    if st != "CLICKED":
        cdp.close()
        fail(f"找不到可点的发布按钮：{st}")
    print("[pub] 已点发布，等待跳转…", file=sys.stderr)
    ok, last_url = False, ""
    for _ in range(20):
        time.sleep(3)
        last_url = cdp.js("location.href") or ""
        if "weitoutiao" in last_url and "/publish" not in last_url:
            ok = True
            break
    # 5) 校验列表首条
    first = ""
    if ok:
        cdp.goto(LIST_URL, wait=5)
        first = cdp.js("document.body.innerText.replace(/\\n+/g,' ').slice(0,240)") or ""
    cdp.close()

    if not ok:
        notify_email("微头条发布可能失败", f"点了发布但 URL 没跳转，最后 URL={last_url}\n正文前 30 字：{paras[0][:30]}")
        fail(f"点了发布但页面没跳到列表页（最后 URL={last_url}），请人工确认是否已发")

    append_ledger(a.topic or paras[0][:16], "已发布（审核中）", paras[0][:60])
    print(json.dumps({"ok": True, "chars": len(filled), "count": got.get("count"),
                      "first_line": paras[0][:40], "list_head": first[:120].replace("\n", " ")},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
