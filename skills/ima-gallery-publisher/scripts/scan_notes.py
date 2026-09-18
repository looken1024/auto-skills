#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""扫描 IMA 新增的「每日图集」笔记，输出待处理清单。

用法: python3 scan_notes.py
输出: 每行一条 "note_id<TAB>title"，无新增输出 NO_NEW
"""
import json, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
LEDGER = HERE / 'data' / 'published_notes.json'
CLIENT = open('/home/ubuntu/.config/ima/client_id').read().strip()
KEY = open('/home/ubuntu/.config/ima/api_key').read().strip()


def ima_post(api_path, body):
    req = urllib.request.Request(f'https://ima.qq.com/{api_path}',
        data=json.dumps(body).encode(),
        headers={'ima-openapi-clientid': CLIENT, 'ima-openapi-apikey': KEY,
                 'ima-openapi-ctx': 'skill_version=1.1.9', 'Content-Type': 'application/json'})
    return json.loads(urllib.request.urlopen(req, timeout=60).read())


def load_ledger():
    if LEDGER.exists():
        return json.loads(LEDGER.read_text(encoding='utf-8'))
    # 已手工发过赵云那篇
    return {'done': ['7506853768494767']}


def main():
    ledger = load_ledger()
    done = set(ledger['done'])
    r = ima_post('openapi/note/v1/search_note',
                 {'search_type': 0, 'query_info': {'title': '每日图集'}, 'start': 0, 'end': 20})
    hits = r.get('data', {}).get('search_note_infos', [])
    new = []
    for h in hits:
        nb = h.get('note_book_info', {})
        nid, title = nb.get('note_id'), nb.get('title', '')
        if nid and nid not in done:
            new.append((nid, title))
    if not new:
        print('NO_NEW')
        return
    for nid, title in new:
        # 只处理真正的图集笔记（标题含"每日图集"），过滤搜索噪音（图片笔记/文档等）
        if '每日图集' in title:
            print(f'{nid}\t{title}')


if __name__ == '__main__':
    main()
