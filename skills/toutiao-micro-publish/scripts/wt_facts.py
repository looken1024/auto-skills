#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给选题抓事实（脚本化）：浏览器搜一遍 → 提取标题+摘要 → 小上下文 LLM 归纳成事实清单。

用法：python3 wt_facts.py --topic "题目" [--out /tmp/wt_facts.json]
输出 JSON：{"facts": ["…", …], "sources": ["…"], "raw_snippets": n}
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wt_common import cdp_tab, llm  # noqa: E402

EXTRACT_JS = """(() => {
  const out = [];
  document.querySelectorAll('li.b_algo, div.result, div.c-container').forEach(li => {
    const a = li.querySelector('h2 a, a');
    const p = li.querySelector('p, .c-abstract');
    if (a && a.innerText.trim()) out.push({t: a.innerText.trim().slice(0,120),
                                          s: (p ? p.innerText.trim() : '').slice(0,220)});
  });
  return JSON.stringify(out.slice(0, 8));
})()"""


def search_bing(cdp, q):
    import urllib.parse
    cdp.goto("https://cn.bing.com/search?q=" + urllib.parse.quote(q), wait=6)
    out = cdp.js(EXTRACT_JS)
    try:
        return json.loads(out or "[]")
    except Exception:
        return []


def search_toutiao(cdp, q):
    import urllib.parse
    cdp.goto("https://so.toutiao.com/search?keyword=" + urllib.parse.quote(q), wait=7)
    js = ("(() => { const a=[...document.querySelectorAll('div[class*=result] div, article')];"
          "return JSON.stringify(a.map(e=>e.innerText.trim()).filter(t=>t.length>20).slice(0,10)"
          ".map(t=>({t:t.slice(0,120), s:t.slice(0,240)}))); })()")
    out = cdp.js(js)
    try:
        return json.loads(out or "[]")
    except Exception:
        return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", required=True)
    ap.add_argument("--out", default="/tmp/wt_facts.json")
    a = ap.parse_args()

    cdp, _ = cdp_tab(prefer_host=None, new_url="about:blank")
    res = []
    for fn in (search_bing, search_toutiao):
        try:
            res = fn(cdp, a.topic)
        except Exception as e:
            print(f"[facts] 搜索异常 {type(e).__name__}: {str(e)[:80]}", file=sys.stderr)
            res = []
        if len(res) >= 3:
            break
    cdp.close()

    if not res:
        print("[facts] 没抓到搜索结果，退回空事实清单（写稿只用常识表述）", file=sys.stderr)
        json.dump({"facts": [], "sources": [], "raw_snippets": 0}, open(a.out, "w", encoding="utf-8"),
                  ensure_ascii=False)
        print("[]")
        return

    blob = "\n".join(f"- {r['t']}｜{r['s']}" for r in res[:8])
    prompt = f"""下面是关于「{a.topic}」的搜索结果片段（可能含噪音、广告、旧闻）。请只做一件事：提炼出**能站得住的客观事实**，供写稿使用。

{blob}

要求：
- 只保留有具体信息量的事实：数字、金额、时间、地点、机构名、当事人原话
- 一条事实一行，最多 8 条；互相矛盾或明显是广告/评论的丢弃
- 拿不准的不要写；宁可少
- 每条后面用括号标出来源关键词（如：央视、某报、当事公司公告）
- 只输出 JSON：{{"facts":["…"],"sources":["域名或媒体名，最多5个"]}}
- 如果这些片段里根本没有可用事实，就返回 {{"facts":[],"sources":[]}}"""
    txt, model = llm(prompt, max_tokens=900, temperature=0.3)
    m = re.search(r"\{.*\}", txt, re.S)
    data = {"facts": [], "sources": []}
    if m:
        try:
            data = json.loads(m.group(0))
        except Exception:
            pass
    data["raw_snippets"] = len(res)
    data["_model"] = model
    json.dump(data, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(data, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
