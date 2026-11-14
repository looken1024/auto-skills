#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校验步骤图输出一致性：所有图同尺寸、字号同为基准值。

用法:
  python3 verify_outputs.py steps.json out

exit 0 = 一致；exit 1 = 有缺图或尺寸不一致（字号变小只告警，长文案会自动缩）。
"""
import json
import os
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import recipe_step_text as R  # noqa: E402


def main():
    if len(sys.argv) < 2:
        sys.exit("用法: verify_outputs.py steps.json [outdir]")
    steps = json.load(open(sys.argv[1], encoding="utf-8"))
    outdir = sys.argv[2] if len(sys.argv) > 2 else "out"

    sizes, font_sizes, missing = set(), set(), []
    for s in steps:
        p = os.path.join(outdir, f"{s['step']}.jpg")
        if not os.path.exists(p):
            missing.append(p)
            continue
        im = Image.open(p)
        d = ImageDraw.Draw(im)
        f, lines, _ = R.fit_font(d, s["text"], int(im.width * 0.86),
                                 int(im.height * 0.32), int(im.width * R.FONT_RATIO))
        sizes.add(im.size)
        font_sizes.add(f.size)
        print(s["step"], im.size, "字号", f.size, "行数", len(lines))

    print("尺寸:", sorted(sizes), "字号:", sorted(font_sizes))
    if missing:
        print("缺图:", missing)
        return 1
    if len(sizes) > 1:
        print("✗ 尺寸不一致，检查底图是否有的没有等比缩到统一宽度")
        return 1
    if len(font_sizes) > 1:
        print("⚠ 字号不一致：通常是某条文案太长触发了自动缩小，压短文案即可")
    return 0


if __name__ == "__main__":
    sys.exit(main())
