#!/usr/bin/env python3
"""AI 味终检器：公众号文章初稿生成后，调用强模型（默认 kimi-k3）检查标题与正文的 AI 味。

用法:
  python3 ai_taste_check.py <article.md> ['标题1' '标题2' '标题3'] [--model <id>]

- 默认模型 kimi-k3；可 --model glm-5.3 / deepseek-v4-flash 切换（kimi/glm 上游抖动时备用，实测 deepseek-v4-flash 最稳）
- 从 ~/.openclaw/openclaw.json 读 custom_go provider 的真实 key
- 通过 curl 调用（urllib 会被 Cloudflare 拦，error 1010）
- 只读不改：输出检查报告，由写作者决定是否采纳修改
"""
import json, os, subprocess, sys

CONFIG = os.path.expanduser("~/.openclaw/openclaw.json")
MODEL = "kimi-k3"

def find_go_key(o):
    """递归找 baseUrl 含 opencode 的 provider 节点，取其 apiKey"""
    if isinstance(o, dict):
        if isinstance(o.get("baseUrl"), str) and "opencode" in o["baseUrl"] and "apiKey" in o:
            return o["baseUrl"].rstrip("/"), o["apiKey"]
        for v in o.values():
            r = find_go_key(v)
            if r:
                return r
    elif isinstance(o, list):
        for v in o:
            r = find_go_key(v)
            if r:
                return r
    return None

def main():
    global MODEL
    args = sys.argv[1:]
    if "--model" in args:
        i = args.index("--model")
        MODEL = args[i + 1]
        del args[i:i + 2]
    if not args:
        print("用法: python3 ai_taste_check.py <article.md> ['标题1' '标题2' '标题3'] [--model <id>]")
        sys.exit(1)

    art_path = args[0]
    titles = args[1:] or []
    article = open(art_path, encoding="utf-8").read()
    # 正文最多喂前 4000 字，标题区单独处理
    body = article[:4000]

    found = find_go_key(json.load(open(CONFIG)))
    if not found:
        print("ERROR: 未找到 custom_go (opencode) provider 的 apiKey")
        sys.exit(1)
    base, key = found

    t_lines = "\n".join(f"{i+1}. {t}" for i, t in enumerate(titles)) or "（未提供候选标题）"
    prompt = f"""你是公众号「棱镜折射」的主编，以挑剔、毒舌、反 AI 味的眼光审查一篇投稿。逐项检查并输出：

一、标题审查（重点）
{t_lines}
对每个标题：评级 AI味程度（高/中/低）+ 一句理由 + 若为高/中给出改写建议。
标准：禁用打工人/内卷/社畜式强行现代化梗；禁用"一个人最大的XX，是XX"鸡汤排比式；禁用"历史启示录/不得不看的道理"空泛式；悬念/反差/代入式且有具体信息量为佳。

二、正文 AI 味扫描
逐条列出命中项（引用原文），按这些类型归类：
1. 套话开头（"值得注意的是/需要指出的是/值得一提的是/总的来说/随着XX的发展"）
2. 空修饰（"丰富的/强大的/灵活的/深刻的"堆砌）
3. 排比空转（句句排比无实义）
4. 强行升华结尾（无具体指向的"值得深思"式收尾）
5. 翻译腔/论文腔句子
6. 史实或事实表述疑点（如果发现）

三、修改建议
对每个命中项给出具体改写（一句话内，口语化、有判断、像真人写的）。

[文章正文]
{body}

输出格式：
## 标题审查
标题1：AI味（高/中/低）——理由；改写：
标题2：...
## 正文问题
1. [类型] "原文引用" → 建议改写
## 结尾总评
一句话总评 + 是否建议返工（是/否）

要求：直接给出审查结论，不要复述任务、不要展示思考过程、不要写"让我分析"之类的开头；**总输出控制在 600 字以内**，只列命中项，没问题的部分不要写分析。"""

    payload = json.dumps({
        "model": MODEL,
        "max_tokens": 2500,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()

    r = subprocess.run(
        ["curl", "-s", "-m", "180",
         "-H", "Authorization: Bearer " + key,
         "-H", "Content-Type: application/json",
         "-d", payload, base + "/chat/completions"],
        capture_output=True, text=True, timeout=190,
    )
    try:
        d = json.loads(r.stdout)
        if "error" in d:
            print("调用失败:", json.dumps(d["error"], ensure_ascii=False)[:300])
            sys.exit(1)
        msg = d["choices"][0]["message"]
        print(msg.get("content") or msg.get("reasoning_content") or "（空响应）")
    except Exception as e:
        print("解析失败:", e)
        print(r.stdout[:500])
        sys.exit(1)

if __name__ == "__main__":
    main()