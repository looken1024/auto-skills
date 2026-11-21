#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 Commons 抓好的图片做成一期公众号图集草稿（news，带小程序链接 + 来源署名）。

用法:
  python3 commons_to_draft.py --picked /tmp/yy_out/picked.json --title "岳阳楼，洞庭湖边的老楼" \
      --credit "图片来自 Wikimedia Commons（CC BY-SA / CC BY / CC0）"
"""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config
import pexels_gallery_draft as P


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--picked", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--credit", default="图片来自 Wikimedia Commons，遵循 CC BY-SA / CC BY / CC0 许可")
    ap.add_argument("--cover", default=None, help="封面图路径（默认取第一张）")
    a = ap.parse_args()

    c = config.get_wechat_config()
    aid, sec = c["app_id"], c["app_secret"]
    picked = json.load(open(a.picked, encoding="utf-8"))
    if len(picked) < 5:
        sys.exit(f"有效图太少：{len(picked)} 张")

    cover_src = a.cover or picked[0]["file"]
    P._shrink_for_upload(cover_src, "/tmp/commons_cover.jpg", max_kb=800)
    cover = P.upload_image_material(aid, sec, "/tmp/commons_cover.jpg")
    thumb = cover.get("media_id")
    if not thumb:
        sys.exit(f"封面上传失败：{cover}")
    print("封面上传 OK", thumb[:24])

    urls = []
    for p in picked:
        P._shrink_for_upload(p["file"], "/tmp/commons_body.jpg", max_kb=900)
        urls.append(P.upload_content_image(aid, sec, "/tmp/commons_body.jpg"))
    print(f"正文图上传 OK {len(urls)} 张")

    blocks = [f'<p><img src="{u}" style="width:100%;"/></p>' for u in urls]
    blocks.append(f'<p style="font-size:12px;color:#888888;">{a.credit}</p>')
    content = "<p><br/></p>".join(blocks) + "<p><br/></p>" + P._link_html()
    draft = P.create_news_draft(aid, sec, a.title, content, thumb)
    print("草稿 OK media_id=", draft.get("media_id"))
    print("图数:", content.count("<img"))


if __name__ == "__main__":
    main()
