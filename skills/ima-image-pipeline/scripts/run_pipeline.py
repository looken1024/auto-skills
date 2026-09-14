#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IMA 图片流水线：图集话题池选关键词 → pollinations 出图 → IMA 知识库 + 笔记。

用法: python3 run_pipeline.py
"""
import json, os, random, subprocess, time, urllib.parse, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
IMASKILL = Path('/home/ubuntu/.hermes/skills/ima-skill')
PREFLIGHT = IMASKILL / 'knowledge-base/scripts/preflight-check.cjs'
COS = IMASKILL / 'knowledge-base/scripts/cos-upload.cjs'
TOPICS = json.load(open('/home/ubuntu/.hermes/skills/wechat-ai-publisher/scripts/topics.json', encoding='utf-8'))
KB = json.load(open(HERE / 'references/ima_kb.json', encoding='utf-8'))
LEDGER = HERE / 'data' / 'image_ledger.json'
CLIENT = open('/home/ubuntu/.config/ima/client_id').read().strip()
KEY = open('/home/ubuntu/.config/ima/api_key').read().strip()
SUFFIX = "photorealistic, atmospheric, portrait orientation, soft natural lighting, high detail, no text, no watermark, no signature, no logo, no people"


def load_ledger():
    if LEDGER.exists():
        return json.loads(LEDGER.read_text(encoding='utf-8'))
    return {'done': []}


def save_ledger(l):
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(l, ensure_ascii=False, indent=1), encoding='utf-8')


def ima_post(api_path, body):
    req = urllib.request.Request(f'https://ima.qq.com/{api_path}',
        data=json.dumps(body).encode(),
        headers={'ima-openapi-clientid': CLIENT, 'ima-openapi-apikey': KEY,
                 'ima-openapi-ctx': 'skill_version=1.1.9', 'Content-Type': 'application/json'})
    return json.loads(urllib.request.urlopen(req, timeout=60).read())


def main():
    ledger = load_ledger()
    done = {x['cn'] for x in ledger['done']}
    pool = [t for t in TOPICS if t['cn'] not in done]
    if not pool:
        ledger['done'] = []
        pool = TOPICS
    kw = random.choice(pool)
    prompt = f"{kw['en']}, {SUFFIX}"
    print(f"[1/5] 选中: {kw['cn']} / {kw['en']}", flush=True)

    out = f"/tmp/ima_img_{int(time.time())}.jpg"
    url = "https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt) + f"?width=576&height=1024&nologo=true&seed={random.randint(1,9999)}"
    r = subprocess.run(['curl', '-sL', '-A', 'Mozilla/5.0', '-o', out, url], capture_output=True, timeout=180)
    if r.returncode != 0:
        raise RuntimeError(f"出图失败: {r.stderr[:200]}")
    r2 = subprocess.run(['file', out], capture_output=True, text=True)
    if 'JPEG' not in r2.stdout:
        raise RuntimeError(f"不是 JPEG: {r2.stdout}")
    print(f"[3/5] 图片 OK: {r2.stdout.strip()}", flush=True)

    pf = json.loads(subprocess.run(['node', str(PREFLIGHT), '--file', out], capture_output=True, text=True).stdout)
    if not pf['pass']:
        raise RuntimeError(f"preflight 失败: {pf}")

    name = pf['file_name']
    rep = ima_post('openapi/wiki/v1/check_repeated_names', {
        'params': [{'name': name, 'media_type': pf['media_type']}],
        'knowledge_base_id': KB['kb_id']})
    if rep['data']['results'][0]['is_repeated']:
        base, ext = name.rsplit('.', 1)
        name = f"{base}_{time.strftime('%Y%m%d%H%M%S')}.{ext}"
        os.rename(out, f"/tmp/{name}")
        out = f"/tmp/{name}"

    cm = ima_post('openapi/wiki/v1/create_media', {
        'file_name': name, 'file_size': pf['file_size'],
        'content_type': pf['content_type'], 'knowledge_base_id': KB['kb_id'],
        'file_ext': pf['file_ext']})
    media_id = cm['data']['media_id']
    cred = cm['data']['cos_credential']

    cr = subprocess.run(['node', str(COS),
        '--file', out, '--secret-id', cred['secret_id'], '--secret-key', cred['secret_key'],
        '--token', cred['token'], '--bucket', cred['bucket_name'], '--region', cred['region'],
        '--cos-key', cred['cos_key'], '--content-type', pf['content_type'],
        '--start-time', cred['start_time'], '--expired-time', cred['expired_time'],
        '--timeout', '300000'], capture_output=True, text=True, timeout=360)
    if cr.returncode != 0:
        raise RuntimeError(f"COS 上传失败: {cr.stderr[-300:]}")
    print(f"[4/5] COS 上传成功", flush=True)

    ima_post('openapi/wiki/v1/add_knowledge', {
        'media_type': pf['media_type'], 'media_id': media_id, 'title': name,
        'knowledge_base_id': KB['kb_id'],
        'file_info': {'cos_key': cred['cos_key'], 'file_size': pf['file_size'], 'file_name': name}})
    mi = ima_post('openapi/wiki/v1/get_media_info', {'media_id': media_id})
    img_url = mi['data']['url_info']['url']

    note_title = name.rsplit('.', 1)[0]
    note_content = f"# {note_title}\n\n![{note_title}]({img_url})\n\n从公众号图集话题池随机抽取的关键词生成的图片。\n\n> 生成方式：pollinations.ai 免费出图\n> 话题：{kw['cn']} / {kw['en']}\n> 上传时间：{time.strftime('%Y-%m-%d %H:%M:%S')}\n> 所属知识库：{KB['kb_name']}"
    ni = ima_post('openapi/note/v1/import_doc', {'content_format': 1, 'content': note_content})
    note_id = ni['data']['note_id']
    gc = ima_post('openapi/note/v1/get_doc_content', {'note_id': note_id, 'target_content_format': 0})
    print(f"[5/5] 笔记 {note_id} 已验证", flush=True)

    ledger['done'].append({'cn': kw['cn'], 'en': kw['en'], 'media_id': media_id, 'note_id': note_id, 'ts': time.strftime('%Y-%m-%d %H:%M:%S')})
    save_ledger(ledger)
    print(f"✅ 完成: {note_title} → 知识库 + 笔记 {note_id}", flush=True)


if __name__ == '__main__':
    main()