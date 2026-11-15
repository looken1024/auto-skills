# 小程序云环境探查 — 数据库与存储结构

## 环境

- 云环境：`cloud1-d9gkyv32i776bf4cc`
- AppID：`wx489060715b335aaf`
- COS 桶：`636c-cloud1-d9gkyv32i776bf4cc-1312191845`（ap-shanghai）

## 数据库 API 路径命名规则

云开发 HTTP API 的路径**不是** `/tcb/database/<name>` 格式，而是全小写拼接：

| 接口 | 正确路径 | 状态 |
|------|----------|------|
| 列集合 | `POST /tcb/databasecollectionget` | ✅ 通 |
| 查询记录 | `POST /tcb/databasequery` | ❌ 47001 |
| 插入记录 | `POST /tcb/databaseadd` | ❌ 47001 |
| 统计数量 | `POST /tcb/databasecount` | ❌ 47001 |
| 更新记录 | `POST /tcb/databaseupdate` | ❌ 47001 |
| 删除记录 | `POST /tcb/databasedelete` | ❌ 47001 |
| 聚合 | `POST /tcb/databaseaggregate` | ❌ 47001 |
| 导出数据 | `POST /tcb/databasemigrateexport` | ✅ 通 |
| 导出状态 | `POST /tcb/databasemigratequeryinfo` | ✅ 通 |

⚠️ `/tcb/database/...`（含 database 段）全部返回 40066 `invalid url`。

## databasequery 47001 诊断

`databasequery` / `databaseadd` / `databasecount` 等读写接口全部返回 47001 `data format error`，**与 body 格式无关**。试过的格式：

- `query` 作为 JSON 对象 `{}`
- `query` 作为 JSON 字符串 `"{}"`
- `query` 作为 JS 表达式 `"db.collection('images').limit(3).get()"`
- 含/不含 `limit`、`offset`、`projection`
- 含/不含 `appid`
- `access_token` vs `cloudbase_access_token`（后者返回 40014）

**结论**：当前账号的 `access_token`（`/cgi-bin/token`）只能调元数据和导出接口，不能做 CRUD。需要 `cloudbase_access_token`（`/tcb/gettoken`），但该接口对当前 AppID 返回 40066 `invalid url`——可能需在云开发控制台开通数据库读写权限。

## 可用替代方案：数据导出

`databasemigrateexport` + `databasemigratequeryinfo` 可以读取集合数据：

```python
# 1. 发起导出
r = requests.post(
    f"https://api.weixin.qq.com/tcb/databasemigrateexport?access_token={tok}",
    json={
        "env": ENV,
        "file_path": "gallery-test/export_images",  # 导出到云存储的路径
        "file_type": 1,  # 1=JSON
        "query": "db.collection('images').limit(3).get()"  # JS 表达式
    }, timeout=30
).json()
job_id = r["job_id"]

# 2. 轮询状态
status = requests.post(
    f"https://api.weixin.qq.com/tcb/databasemigratequeryinfo?access_token={tok}",
    json={"env": ENV, "job_id": job_id}, timeout=15
).json()
# status == "waiting" → 继续轮询；"success" → file_url 可下载

# 3. 下载结果（NDJSON 格式，每行一条记录）
url = status["file_url"]
data = requests.get(url, timeout=30).text
for line in data.strip().split("\n"):
    record = json.loads(line)
```

## images 集合字段

从导出数据读到的完整 schema：

| 字段 | 类型 | 说明 |
|------|------|------|
| `_id` | string | 文档 ID |
| `_openid` | string | 上传者微信 ID |
| `thumbnailFileID` | string | 缩略图 file_id |
| `originalFileID` | string | 原图 file_id |
| `title` | string | 标题 |
| `category` | string | 分类 |
| `categories` | array | 分类数组 |
| `tags` | array | 标签 |
| `width` | number | 原图宽度 |
| `height` | number | 原图高度 |
| `uploadTime` | date | 上传时间 |
| `downloads` | number | 下载次数 |
| `status` | number | 状态 |
| `reviewer` | string | 审核人 |
| `reviewTime` | date/null | 审核时间 |

## 存储目录结构

从 `originalFileID` / `thumbnailFileID` 的路径模式：

```
原图:   images/original/<timestamp>-<random>.jpg
缩略图: images/thumbnails/<timestamp>-<random>.jpg
```

完整 file_id 示例：

```
cloud://cloud1-d9gkyv32i776bf4cc.636c-cloud1-d9gkyv32i776bf4cc-1312191845/images/original/1790320786526-jocqlor83.jpg
cloud://cloud1-d9gkyv32i776bf4cc.636c-cloud1-d9gkyv32i776bf4cc-1312191845/images/thumbnails/1790320786526-jocqlor83.jpg
```

## 集合概览

| 集合 | 文档数 | 大小 |
|------|--------|------|
| `images` | 21 | 11,860 字节 |
| `users` | 1 | 316 字节 |
