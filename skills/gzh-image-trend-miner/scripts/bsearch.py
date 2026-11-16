#!/usr/bin/env python3
"""Bing 直连搜索（绕过失效的 127.0.0.1:9981 代理），输出 title/url/snippet。

用法：python3 bsearch.py "查询1" "查询2"
web_search 全后端 SSL EOF 时用它兜底；查中文官媒/壁纸站时优先直接 curl 栏目页
（人民网图片 http://pic.people.com.cn/、3G壁纸 https://www.3gbizhi.com/wallJR/index_1.html、
搜狗微信 https://weixin.sogou.com/weixin?type=2&query=<词>），比搜索引擎结果更新。
"""
import sys, re, html, subprocess, urllib.parse

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")


def fetch(url):
    p = subprocess.run(["curl", "-s", "--noproxy", "*", "--max-time", "20",
                        "-A", UA, url], capture_output=True)
    return p.stdout.decode("utf-8", "ignore")


def strip(s):
    s = re.sub(r"<[^>]+>", "", s)
    return html.unescape(re.sub(r"\s+", " ", s)).strip()


def search(q, n=6):
    url = "https://cn.bing.com/search?q=" + urllib.parse.quote(q) + "&setlang=zh-CN"
    h = fetch(url)
    out = []
    for block in re.findall(r'<li class="b_algo".*?</li>', h, re.S)[:n]:
        m = re.search(r'<h2>.*?<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', block, re.S)
        if not m:
            continue
        sn = re.search(r'<p[^>]*>(.*?)</p>', block, re.S)
        out.append((strip(m.group(2)), m.group(1), strip(sn.group(1)) if sn else ""))
    return out


if __name__ == "__main__":
    for q in sys.argv[1:]:
        print("=" * 18, q)
        for t, u, s in search(q):
            print("-", t)
            print("  ", s[:200])
            print("  ", u[:110])
