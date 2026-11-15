---
name: wx-cloud-storage
description: 微信小程序云存储转存：uploadfile→COS上传→batchdownloadfile验证入库。
---

# 微信小程序云存储转存

把外部文件（Pexels 图片、AI 生图、本地文件等）转存到微信小程序云存储（底层 COS），拿到 `file_id` 和临时下载 URL。

## 适用场景

- 图集流程中把处理后的图片转存到云存储（替代/补充微信素材库上传）
- 需要 `file_id` 写入数据库或传给小程序前端
- 需要临时下载链接（`max_age` 秒）供前端拉取

## 四步链路（全通，已实测）

### 1. 获取上传凭证

```
POST https://api.weixin.qq.com/tcb/uploadfile?access_token=<token>
Body: {"env": "<cloud_env_id>", "path": "<云存储路径，如 gallery-test/2026-09-25/img.jpg>"}
```

返回关键字段：

| 字段 | 用途 |
|------|------|
| `url` | COS 上传目标 URL |
| `token` | COS security token → `x-cos-security-token` |
| `authorization` | COS 签名 → `Signature` |
| `file_id` | 云存储唯一标识（`cloud://...`） |
| `cos_file_id` | COS 内部 file id → `x-cos-meta-fileid` |

### 2. COS 上传

```
POST <url>  (multipart/form-data)
```

**必须包含五个字段**（缺一不可）：

| 字段 | 值来源 |
|------|--------|
| `key` | 云存储路径（与 step 1 的 path 一致） |
| `Signature` | `authorization` 字段值 |
| `x-cos-security-token` | `token` 字段值 |
| `x-cos-meta-fileid` | `cos_file_id` 字段值 |
| `file` | 文件二进制 |

成功返回 **204**（无 body）。

### 3. 验证入库

```
POST https://api.weixin.qq.com/tcb/batchdownloadfile?access_token=<token>
Body: {"env": "<env>", "file_list": [{"fileid": "<file_id>", "max_age": 7200}]}
```

⚠️ 字段名是 **`fileid`**（不是 `file_id`）。

返回：

```json
{
  "errcode": 0,
  "file_list": [{
    "fileid": "cloud://...",
    "download_url": "https://...tcb.qcloud.la/...?sign=...",
    "status": 0,
    "errmsg": "ok"
  }]
}
```

`status: 0` = 文件存在；`status: 1` + `STORAGE_FILE_NONEXIST` = 未落库（上传失败或 file_id 不对）。

### 4. 清理（可选）

```
POST https://api.weixin.qq.com/tcb/batchdeletefile?access_token=<token>
Body: {"env": "<env>", "fileid_list": ["<file_id>"]}
```

## 坑

- **字段名陷阱**：`uploadfile` 返回 `token` / `authorization` / `cos_file_id` / `file_id`，**不是** `cos` / `fileID` / `cos_filename` / `security_token`。
- **COS 上传必须 multipart/form-data**：不能用 `headers={"Authorization": ...}` + raw body，会报 `MalformedPOSTRequest`。
- **`batchdownloadfile` 用 `fileid`**（不是 `file_id`），否则报 47001 data format error。
- **`batchuploadfile` 不可用**：返回 40066 "invalid url"，只能单文件走 `uploadfile`。
- **`access_token`**：`GET /cgi-bin/token?grant_type=client_credential&appid=<appid>&secret=<secret>`，有效期 7200 秒。
- **云存储路径**不要以 `/` 开头。

## 接入图集流水线

在 `pexels_gallery_draft.py` 的 `process_image` 之后，对每张产出图追加转存：

```python
# 压缩版和全尺寸版都可以转存
for img_path, label in [(c_dst, "compressed"), (full_dst, "full")]:
    cloud_path = f"gallery/{topic}/{date}/{i+1}_{label}.jpg"
    file_id = upload_to_cloud(app_id, app_secret, env, img_path, cloud_path)
```

拿到 `file_id` 后写进最终 JSON 输出，供后续消费。

## 云环境探查（数据库 + 存储结构）

详细记录见 `references/cloud-environment.md`。要点：

- **API 路径命名**：云开发 HTTP API 是全小写拼接（`/tcb/databasecollectionget`），**不是** `/tcb/database/<name>`。后者全部 40066。
- **CRUD 接口不可用**：`databasequery`/`databaseadd`/`databasecount` 等对当前 token 返回 47001，需 `cloudbase_access_token`（当前拿不到）。
- **替代方案**：`databasemigrateexport` + `databasemigratequeryinfo` 可读集合数据（NDJSON 格式）。
- **`images` 集合**：21 条记录，字段含 `originalFileID` / `thumbnailFileID` / `title` / `category` / `width` / `height` / `uploadTime` 等。
- **存储目录**：`images/original/<ts>-<rand>.jpg`（原图）+ `images/thumbnails/<ts>-<rand>.jpg`（缩略图）。

## 配置

- `env`：小程序云环境 ID（如 `cloud1-d9gkyv32i776bf4cc`）
- `appid` + `appsecret`：小程序 AppID 和 AppSecret（用于获取 access_token）
