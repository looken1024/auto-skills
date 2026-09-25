# 小程序云存储转存 — 实测验证记录

## 环境

- 云环境：`cloud1-d9gkyv32i776bf4cc`
- AppID：`wx489060715b335aaf`
- COS 桶：`636c-cloud1-d9gkyv32i776bf4cc-1312191845`（ap-shanghai）

## 实测通过的完整链路

```python
import requests

# 1. token
tok = requests.get("https://api.weixin.qq.com/cgi-bin/token",
    params={"grant_type":"client_credential","appid":APPID,"secret":SECRET}).json()["access_token"]

# 2. uploadfile 凭证
r = requests.post(f"https://api.weixin.qq.com/tcb/uploadfile?access_token={tok}",
    json={"env": ENV, "path": "gallery-test/probe.jpg"}).json()
# r = {"errcode":0, "url":..., "token":..., "authorization":..., "file_id":..., "cos_file_id":...}

# 3. COS multipart 上传
files = {
    "key": (None, "gallery-test/probe.jpg"),
    "Signature": (None, r["authorization"]),
    "x-cos-security-token": (None, r["token"]),
    "x-cos-meta-fileid": (None, r["cos_file_id"]),
    "file": ("probe.jpg", data, "image/jpeg"),
}
up = requests.post(r["url"], files=files)  # → 204

# 4. 验证入库
d = requests.post(f"https://api.weixin.qq.com/tcb/batchdownloadfile?access_token={tok}",
    json={"env": ENV, "file_list": [{"fileid": r["file_id"], "max_age": 7200}]}).json()
# d["file_list"][0]["download_url"] 非空 + status:0 = 成功

# 5. 清理
requests.post(f"https://api.weixin.qq.com/tcb/batchdeletefile?access_token={tok}",
    json={"env": ENV, "fileid_list": [r["file_id"]]})
```

## 实测失败路径（别踩）

| 尝试 | 结果 |
|------|------|
| `headers={"Authorization": auth}` + raw body | 400 `MalformedPOSTRequest` |
| `batchdownloadfile` 用 `file_id` | 47001 `data format error` |
| `batchuploadfile` | 40066 `invalid url` |
| 用 `cos` / `fileID` / `cos_filename` 字段名 | KeyError |
| 上传后立即 `batchdownloadfile` | `STORAGE_FILE_NONEXIST`（文件还没落库） |

## 验证结果

- COS 上传：204
- batchdownloadfile：`status:0`, `download_url` 非空
- GET download_url：200, 334 bytes, md5 `f24c663cbf4c528825e0c0bf1fb8c6b1`
- batchdeletefile：`status:0`
