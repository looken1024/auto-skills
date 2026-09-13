#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""微头条 AI 味复审器：发布前用高级模型挑刺复审，抓 AI 味和可完善点。

用法:
  python3 review_weitoutiao.py <text.md|txt> [--model <id>] [--strict]

- 默认模型 cohere/north-mini-code:free（本机 Hermes 主模型，从 ~/.hermes/.env 读 CUSTOM_CLINE_API_KEY，Cline API）
- 可 --model <id> 切换（走同一 Cline endpoint）
- 通过 curl 调用（https://api.cline.bot/api/v1/chat/completions）
- 只读不改：输出复审报告，命中的 AI 味必须改写后重跑，直到通过才允许发布
- 失败自动切换到下一个模型重试（倒序依次尝试）
"""
import json, os, subprocess, sys

ENV_FILE = os.path.expanduser("~/.hermes/.env")
BASE = "https://api.cline.bot/api/v1"

# 默认模型列表（按 2026-09-13 free 模型横评结果排序：前面的经过实测“能挑出 AI 味且不误报”
DEFAULT_MODELS = [
    "cohere/north-mini-code:free",              # 本机主模型，实测调刺准+对好文不误报，~10s
    "nvidia/nemotron-3-super-120b-a12b:free",   # 实测第二优：不误报、B长度合规，但慢 ~70s
    "dots-studio/dots-3-note-preview:free",     # 不误报，写作偏长
    "google/gemma-4-26b-a4b-it:free",           # 写作文笔最好（写稿首选），但复审偏严
    "nex-agi/nex-n2.5-pro:free",                # 审稿细但慢(~80s)，有超时风险
    "thinkingmachines/inkling:free",
    "thinkingmachines/inkling-small:free",
    "inclusionai/ling-3.0-flash-sante:free",
    "inclusionai/ling-3.0-flash-fin:free",
    "nex-agi/nex-n2.5-mini:free",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "poolside/laguna-s-2.1:free",
    "poolside/laguna-xs-2.1:free",
    "liquid/lfm-2.5-2.6b:free",
    "google/gemma-4-31b-it:free",
    "inclusionai/ling-3.0-flash-vl:free",
    "nvidia/nemotron-3.5-content-safety:free",  # 实测基本不干活（输出 15-52 字），仅兼底
    "nvidia/nemotron-3.5-lightning:free",       # 慢/易超时
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",  # 常 500
    "openrouter/free",
    "z-ai/glm-5.3-flash",                       # 实测 429 限流
]

def load_key():
    try:
        for line in open(ENV_FILE, encoding="utf-8"):
            line = line.strip()
            if line.startswith("CUSTOM_CLINE_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    return None

def call_model_with_fallback(text, models, start_index=0, strict=False, used_models=None):
    """递归调用模型，失败自动切换下一个"""
    if used_models is None:
        used_models = []
    
    if start_index >= len(models):
        print(f"错误：所有 {len(DEFAULT_MODELS)} 个模型都失败了，已尝试：{' -> '.join(used_models)}")
        sys.exit(1)
    
    current_model = models[start_index]
    used_models.append(current_model)
    
    print(f"尝试模型 {current_model} ({start_index + 1}/{len(models)})")
    
    key = load_key()
    if not key:
        print("ERROR: ~/.hermes/.env 中未找到 CUSTOM_CLINE_API_KEY")
        sys.exit(1)
    
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
7. 短视频套路梗/网感短句（2026-08-26 用户点名禁用）："正在偷你的底裤""套路就三样""翻译成人话""翻翻名单，个个都是人才""这事离谱在哪""一个比一个会玩""谁懂啊""绝了"等刻意设计的短句梗——这类看似口语、实则堆砌网感，比套话更 AI 味；口语化要自然，不靠这类金句撑场

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
        "model": current_model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }).encode()

    r = subprocess.run(
        ["curl", "-s", "-m", "180",
         "-H", "Authorization: " + "Bearer" + " " + key.strip(),
         "-H", "Content-Type: application/json",
         "-d", payload, BASE + "/chat/completions"],
        capture_output=True, text=True, timeout=190,
    )
    
    try:
        d = json.loads(r.stdout)
        if "error" in d and "choices" not in d:
            error_msg = d.get("error", {}).get("message", "未知错误")
            print(f"模型 {current_model} 调用失败：{error_msg}")
            return call_model_with_fallback(text, models, start_index + 1, strict, used_models)
        
        d = d.get("data", d)
        msg = d["choices"][0]["message"]
        content = (msg.get("content") or "").strip()
        reasoning = (msg.get("reasoning") or msg.get("reasoning_content") or "").strip()
        
        if not content:
            print(f"模型 {current_model} 未返回正文，仅思考过程，切换下一个模型")
            return call_model_with_fallback(text, models, start_index + 1, strict, used_models)
        
        # 输出成功内容
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
        elif re.search(r"建议返工[：:]?\s*是", content):
            print("\n【复审结论】返工")
        elif re.search(r"不返工|不必返工|无需返工|不用返工|不需返工|不建议返工|不建议重写|无需重写|返工[：:]\s*否", content):
            print("\n【复审结论】不返工")
        else:
            print("\n【复审结论】未识别，需人工确认")
        
        print(f"\n✅ 成功使用模型 {current_model}，已完成复审任务")
        print(f"📝 尝试顺序：{' -> '.join(used_models)}")
        return True
        
    except Exception as e:
        print(f"模型 {current_model} 解析失败：{e}")
        return call_model_with_fallback(text, models, start_index + 1, strict, used_models)

def main():
    args = sys.argv[1:]
    strict = False
    selected_model = None
    
    if "--model" in args:
        i = args.index("--model")
        selected_model = args[i + 1]
        del args[i:i + 2]
    
    if "--strict" in args:
        strict = True
        args.remove("--strict")
    
    if not args:
        print("用法: python3 review_weitoutiao.py <text.md|txt> [--model <id>] [--strict]")
        sys.exit(1)
    
    text = open(args[0], encoding="utf-8").read().strip()
    if len(text) > 1200:
        text = text[:1200]
    
    # 决定尝试的模型列表
    models_to_try = []
    if selected_model:
        if selected_model in DEFAULT_MODELS:
            # 如果用户指定了模型，从该模型开始尝试（包括它自己）
            start_idx = DEFAULT_MODELS.index(selected_model)
            models_to_try = DEFAULT_MODELS[start_idx:]
        else:
            # 如果用户指定了不在列表中的模型，先尝试它，再继续默认列表
            models_to_try = [selected_model] + DEFAULT_MODELS
    else:
        models_to_try = DEFAULT_MODELS
    
    print(f"开始复审任务，优先级模型列表：{' -> '.join(models_to_try)}")
    
    success = call_model_with_fallback(text, models_to_try, strict=strict)
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()
