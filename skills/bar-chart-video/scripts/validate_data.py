#!/usr/bin/env python3
"""
validate_data.py - 数据校验工具(配合模型人工审)
- 检查数据结构:values数量=年份数、无负数、无全0国家
- 输出:每年Top N、国家进出榜事件、异常检测(数据是否"合理")
- 校验报告交给视觉/文本模型审查,通过后才生成视频
用法:python3 validate_data.py <data.json> [--top 5]
"""
import argparse, json

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    ap.add_argument("--top", type=int, default=5)
    args = ap.parse_args()

    data = json.load(open(args.data, encoding="utf-8"))
    years = data.get("years") or list(range(data["start_year"], data["end_year"] + 1))
    n = len(years)
    items = data["items"]

    problems = []
    # 结构检查
    for it in items:
        vals = it["values"]
        if len(vals) != n:
            problems.append(f"❌ {it['name']}: values数量 {len(vals)} ≠ 年份数 {n}")
            continue
        if any(v < 0 for v in vals):
            problems.append(f"❌ {it['name']}: 存在负值")
        if all(v == 0 for v in vals):
            problems.append(f"⚠️ {it['name']}: 全0(可能整段不该出现)")
        # 数值突变检测(年增幅/降幅超50%视为异常)
        for i in range(1, n):
            if vals[i-1] > 0 and vals[i] > 0:
                chg = (vals[i] - vals[i-1]) / vals[i-1]
                if abs(chg) > 0.5:
                    problems.append(f"⚠️ {it['name']} {years[i]}年: 变化 {chg*100:.0f}% 异常大(值 {vals[i-1]}→{vals[i]})")

    # 每年 Top N + 进出榜事件
    report = []
    span = f"{years[0]}-{years[-1]}" if len(years) > 1 else str(years[0])
    report.append(f"数据源: {data.get('subtitle','')} | 年份 {span}({len(years)}届) | 实体 {len(items)} 个")
    prev_top = set()
    for i, y in enumerate(years):
        cur = sorted([(it["name"], it["values"][i]) for it in items], key=lambda x: -x[1])
        top = cur[:args.top]
        top_names = {t[0] for t in top if t[1] > 0}
        if i > 0:
            for nm in sorted(top_names - prev_top):
                report.append(f"🏷️ {y}年: {nm} 新进入前{args.top}")
            for nm in sorted(prev_top - top_names):
                report.append(f"🏷️ {y}年: {nm} 跌出前{args.top}")
        prev_top = top_names
        if i % 5 == 0 or y == years[-1]:
            report.append(f"{y}: " + " | ".join(f"{nm}({v:,.0f})" for nm, v in top))

    # 榜首更替检测
    lead = None
    for i, y in enumerate(years):
        cur = sorted([(it["name"], it["values"][i]) for it in items], key=lambda x: -x[1])
        if cur[0][1] > 0:
            nm = cur[0][0]
            if nm != lead:
                report.append(f"👑 {y}年: 榜首更替 → {nm} ({cur[0][1]:,.0f})")
                lead = nm

    print("\n".join(report))
    print("\n=== 问题清单 ===")
    if problems:
        print("\n".join(problems))
        print(f"\n共 {len(problems)} 个问题")
    else:
        print("✅ 无结构问题")

if __name__ == "__main__":
    main()