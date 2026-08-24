#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""微头条 AI 味复审器：发布前用高级模型挑刺复审，抓 AI 味和可完善点。

用法:
  python3 review_weitoutiao.py <text.md|txt> [--model <id>] [--strict]

- 默认模型 glm-5.3（高级模型，从 openclaw.json 的 custom_go provider 读取 key）
- 可 --model deepseek-v4-pro / minimax-m3 / qwen3.8-max 切换
- 通过 curl 调用（opencode baseUrl + /chat/completions）
- 只读不改：输出复审报告，命中的 AI 味必须改写后重跑，直到通过才允许发布
"""
import json, os, subprocess, sys

CONFIG = os.path.expanduser("~/.openclaw/openclaw.json")
MODEL = "glm-5.3"

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
    strict = False
    if "--model" in args:
        i = args.index("--model")
        MODEL = args[i + 1]
        del args[i:i + 2]
    if "--strict" in args:
        strict = True
        args.remove("--strict")
    if not args:
        print("用法: python3 review_weitoutiao.py <text.md|txt> [--model <id>] [--strict]")
        sys.exit(1)

    text = open(args[0], encoding="utf-8").read().strip()
    # 微头条 500 字上下，一次全喂
    if len(text) > 1200:
        text = text[:1200]

    found = find_go_key(json.load(open(CONFIG)))
    if not found:
        print("ERROR: 未找到 custom_go (opencode) provider 的 apiKey")
        sys.exit(1)
    base, key = found

    strict_note = "（严格模式：宁严勿松，任何疑似 AI 味都要标出）" if strict else ""
    prompt = f"""你是今日头条微头条主编「棱镜折射」的审稿人，以挑剔、毒舌、反 AI 味的眼光复审一篇微头条。这篇文风定位：口语化短句、有情绪有态度有反讽、夹方言感、数字具体、结尾开放抛问题/引导转发。逐项检查并输出：

一、AI 味扫描（重点）
逐条列出命中项（引用原文短句），按类型归类：
1. 套话开头（"近日/随着/引发广泛关注/值得注意的是/需要指出的是"）
2. 空泛修饰（"丰富的/强大的/深刻的/令人深思"类，或"很多钱/大量网友"这类虚指）
3. 排比空转 / 正确但无聊的并列句
4. 强行升华结尾（无具体指向的总结式收尾、喊口号）
5. 翻译腔/新闻通稿腔（"这一事件""背后折射出""带动XX经济"）
6. 不口语化的书面词（"竟然""堪称""可谓"滥用）

二、可完善点
- 开头钩子够不够抓人（前 2 句有没有画面/反差/数字）
- 人物原话或关键数字用没用上；有没有数字该具体却含糊的
- 方言感/反讽是自然还是硬凹
- 结尾问题是否够开放、够勾评论
- 节奏：有没有可删的废话句

三、结论
- 是否建议返工（是/否）
- 若"否"，给 1-2 条"锦上添花"小建议（可选改）

[微头条正文]
{text}

{strict_note}
要求：直接给审查结论，不要复述任务、不要展示思考过程、不要写"让我分析"开头；**总输出控制在 500 字以内**，只列命中项，没问题的部分不写。"""

    payload = json.dumps({
        "model": MODEL,
        "max_tokens": 2000,
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
        content = (msg.get("content") or "").strip()
        reasoning = (msg.get("reasoning_content") or "").strip()
        if not content:
            # 模型只吐了思考过程：不 dump 全文（会污染下游解析），截末尾 + 退出码 2 提示重跑/换模型
            print("（模型未返回正文，仅思考过程，截取末尾 800 字供参考）")
            print(reasoning[-800:] if reasoning else "（空响应）")
            sys.exit(2)
        # 输出截断，防止思考过程撑爆 exec 输出
        if len(content) > 3000:
            print(content[:1500])
            print("\n...[中间省略]...\n")
            print(content[-1000:])
        else:
            print(content)
        # 机器可读结论行，供下游 grep【复审结论】
        import re
        m = re.search(r"结论[：:].{0,6}建议?返工[：:]?(是|否)", content)
        if m:
            print("\n【复审结论】" + ("返工" if m.group(1) == "是" else "不返工"))
        elif "不返工" in content or "无需返工" in content:
            print("\n【复审结论】不返工")
        elif re.search(r"建议返工[：:]?\s*是", content):
            print("\n【复审结论】返工")
        else:
            print("\n【复审结论】未识别，需人工确认")
    except Exception as e:
        print("解析失败:", e)
        print(r.stdout[:500])
        sys.exit(1)

if __name__ == "__main__":
    main()
