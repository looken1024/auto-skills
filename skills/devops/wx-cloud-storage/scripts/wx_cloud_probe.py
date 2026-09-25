#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信小程序云存储转存 — 可复用探针脚本。

用法:
  python3 wx_cloud_probe.py --env <cloud_env_id> --appid <wx_appid> --secret <appsecret> \
    --local-file /path/to/test.jpg --cloud-path gallery-test/probe.jpg

四步全跑：token → uploadfile 凭证 → COS multipart 上传 → batchdownloadfile 验证入库。
退出码 0 = 全链路通过。
"""
import argparse, json, sys, os
import requests


def get_token(appid, secret):
    r = requests.get("https://api.weixin.qq.com/cgi-bin/token",
                     params={"grant_type": "client_credential", "appid": appid, "secret": secret},
                     timeout=15)
    r.raise_for_status()
    tok = r.json().get("access_token")
    if not tok:
        sys.exit(f"获取 access_token 失败: {r.text}")
    return tok


def upload_to_cloud(token, env, local_path, cloud_path):
    """返回 file_id。内部完成 uploadfile + COS multipart 上传。"""
    r = requests.post(f"https://api.weixin.qq.com/tcb/uploadfile?access_token={token}",
                      json={"env": env, "path": cloud_path}, timeout=15).json()
    if r.get("errcode") != 0:
        sys.exit(f"uploadfile 失败: {r}")

    with open(local_path, "rb") as f:
        data = f.read()
    files = {
        "key": (None, cloud_path),
        "Signature": (None, r["authorization"]),
        "x-cos-security-token": (None, r["token"]),
        "x-cos-meta-fileid": (None, r["cos_file_id"]),
        "file": (os.path.basename(cloud_path), data, "image/jpeg"),
    }
    up = requests.post(r["url"], files=files, timeout=30)
    if up.status_code != 204:
        sys.exit(f"COS 上传失败: {up.status_code} {up.text[:300]}")
    return r["file_id"]


def verify_file(token, env, file_id):
    """返回 download_url。status:0 且 url 非空 = 文件已入库。"""
    d = requests.post(f"https://api.weixin.qq.com/tcb/batchdownloadfile?access_token={token}",
                      json={"env": env, "file_list": [{"fileid": file_id, "max_age": 7200}]},
                      timeout=15).json()
    if d.get("errcode") != 0:
        sys.exit(f"batchdownloadfile 失败: {d}")
    entry = d["file_list"][0]
    if entry.get("status") != 0 or not entry.get("download_url"):
        sys.exit(f"文件未入库: {entry}")
    return entry["download_url"]


def main():
    ap = argparse.ArgumentParser(description="微信小程序云存储转存探针")
    ap.add_argument("--env", required=True, help="云环境 ID")
    ap.add_argument("--appid", required=True, help="小程序 AppID")
    ap.add_argument("--secret", required=True, help="小程序 AppSecret")
    ap.add_argument("--local-file", required=True, help="本地待转存文件")
    ap.add_argument("--cloud-path", required=True, help="云存储路径（不以 / 开头）")
    args = ap.parse_args()

    tok = get_token(args.appid, args.secret)
    print(f"[1/3] token OK")

    fid = upload_to_cloud(tok, args.env, args.local_file, args.cloud_path)
    print(f"[2/3] COS 上传 OK  file_id={fid}")

    url = verify_file(tok, args.env, fid)
    print(f"[3/3] 入库验证 OK  download_url={url[:80]}...")
    print(json.dumps({"status": "success", "file_id": fid, "download_url": url}, ensure_ascii=False))


if __name__ == "__main__":
    main()
