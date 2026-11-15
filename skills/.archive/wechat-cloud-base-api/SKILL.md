---
name: "wechat-cloud-base-api"
description: "微信小程序云开发 HTTP API 速查：数据库 CRUD、云存储上传/下载、token 获取、常见踩坑。"
---

# 微信小程序云开发 HTTP API

云开发 HTTP API 让你在服务器端（非小程序端）操作云数据库和云存储。

## 接口清单

所有接口 POST，路径全小写。

| 接口 | 路径 | 用途 |
|------|------|------|
| 获取 token | `POST /cgi-bin/stable_token` | body: `{"grant_type":"client_credential","appid":"...","secret":"..."}` |
| 集合列表 | `POST /tcb/databasecollectionget` | body: `{"env":"...","limit":10,"offset":0}` |
| 查询记录 | `POST /tcb/databasequery` | body: `{"env":"...","query":"db.collection('xxx').limit(3).get()"}` |
| 插入记录 | `POST /tcb/databaseadd` | body: `{"env":"...","query":"db.collection('xxx').add({data:[{...}]})"}` |
| 删除记录 | `POST /tcb/databaseDelete` | body: `{"env":"...","query":"db.collection('xxx').where({...}).remove()"}` |
| 导出数据 | `POST /tcb/databasemigrateexport` | body: `{"env":"...","file_path":"...","file_type":1,"query":"..."}` |
| 导出状态 | `POST /tcb/databasemigratequeryinfo` | body: `{"env":"...","job_id":123}` |
| 上传凭证 | `POST /tcb/uploadfile` | body: `{"env":"...","path":"images/original/xxx.jpg"}` |
| 批量下载 | `POST /tcb/batchdownloadfile` | body: `{"env":"...","file_list":[{"fileid":"cloud://...","max_age":7200}]}` |
| 批量删除 | `POST /tcb/batchdeletefile` | body: `{"env":"...","fileid_list":["cloud://..."]}` |

## 关键踩坑

### 1. 路径全小写
`/tcb/databasecollectionget` 不是 `/tcb/database/collectionget`。中间的 `database` 不是路径段。

### 2. databasequery / databaseadd 只有 env + query
body 里**不能有 `collection` 字段**。query 是 JS 表达式字符串：

{"env":"cloud1-xxx","query":"db.collection('images').limit(3).get()"}

多传 `collection` 会 47001 data format error。

### 3. stable_token 比 cgi-bin/token 稳定
普通 `cgi-bin/token` 在云开发数据库接口上偶发 40001 "invalid credential"。用 `POST /cgi-bin/stable_token`。

### 4. COS 上传 multipart 格式
五个字段缺一不可：
- `key`：云存储路径
- `Signature`：uploadfile 返回的 `authorization`
- `x-cos-security-token`：uploadfile 返回的 `token`
- `x-cos-meta-fileid`：uploadfile 返回的 `cos_file_id`
- `file`：文件本身

### 5. 导出返回 NDJSON
databasemigrateexport 导出的文件每行一条 JSON 记录，不是单个 JSON 对象。解析时逐行 `json.loads`。

### 6. uploadfile 返回字段
`token` / `authorization` / `cos_file_id` / `file_id`。不是 `cos` / `fileID` / `cos_filename`。

## images 集合字段


_id, _openid, thumbnailFileID, originalFileID, title, category,
categories, tags, width, height, uploadTime, downloads, status,
reviewer, reviewTime


## 存储目录约定


原图:   images/original/<timestamp>-<random8>.jpg
缩略图: images/thumbnails/<timestamp>-<random8>.jpg


## 完整上传+入库示例

python
import requests, json, time

# 1. 获取 token
tok = requests.post("https://api.weixin.qq.com/cgi-bin/stable_token",
    json={"grant_type":"client_credential","appid":"APPID","secret":"SECRET"}).json()["access_token"]

# 2. 上传原图
r = requests.post(f"https://api.weixin.qq.com/tcb/uploadfile?access_token={tok}",
    json={"env":"cloud1-xxx","path":"images/original/test.jpg"}).json()
with open("test.jpg","rb") as f:
    requests.post(r["url"], files={
        "key": (None, "images/original/test.jpg"),
        "Signature": (None, r["authorization"]),
        "x-cos-security-token": (None, r["token"]),
        "x-cos-meta-fileid": (None, r["cos_file_id"]),
        "file": ("test.jpg", f, "image/jpeg"),
    })
original_fid = r["file_id"]

# 3. 写入数据库
q = ("db.collection('images').add({data:[{"
     "title: '测试', category: '风景', categories: ['风景'], tags: [],"
     "originalFileID: '" + original_fid + "', thumbnailFileID: 'cloud://...thumb',"
     "width: 100, height: 100, uploadTime: new Date(),"
     "downloads: 0, status: 1, reviewer: '', reviewTime: null}]})")
requests.post(f"https://api.weixin.qq.com/tcb/databaseadd?access_token={tok}",
    json={"env":"cloud1-xxx","query":q})

