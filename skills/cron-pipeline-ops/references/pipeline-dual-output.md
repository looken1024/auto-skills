# 图集流水线双输出架构：压缩版进草稿箱 + 全尺寸版推给用户

> 沉淀自 2026-09-20 图集流水线（job 9d58e7843134）连续失败与修复。

## 需求

用户要两版图：
1. **草稿箱版**：压缩到 ≤600KB，进微信公众号图片消息草稿
2. **微信发送版**：不压缩、全尺寸，直接发给用户看

两版都必须经过**左右翻转 + 滤镜**处理。

## 架构

```
Pexels 原图下载
  → process_image()（翻转+滤镜，大图先缩到短边2500）
    ├─ 全尺寸版：直接存 save_dir/full_*.jpg（不压缩）
    └─ 压缩版：compress_image() → ≤600KB → 上传微信素材库 → 建 newspaper 草稿
```

## 关键限制：不压缩版不能走微信 API

微信素材库对单图有硬性大小限制，实测 31MB 的图直接返回 `45002 content size out of limit`。所以不压缩的全尺寸图**无法通过 API 发出去**——只能存盘后通过 cron 的 `MEDIA:` 标记直接推给用户（不经过微信接口，不受素材库大小限制）。

## 踩坑记录

### 1. 大图双重编码卡死

`process_image()` 原来对 10-15MB 原图直接 `np.array()` 做噪点处理，内存爆炸 + `compress_image.py` 再次编码，4 分钟定时直接超时。

**修复**：`process_image()` 开头加降采样——短边 >2500 时等比缩到 2500（公众号显示足够，且避免 OOM/超时）。

### 2. compress_image 兜底缺失

`compress_image.py` 的渐进压缩只降质量不降分辨率，质量降到最低 75 还超目标时就原图保存（5MB+），然后 `process_image()` 又以 quality=88 重新编码，双重编码 + 大文件反复 IO。

**修复**：降到最低质量仍超目标时，按 0.8→0.2 比例缩小分辨率直到满足目标大小。

### 3. 变量名不一致

补丁引入 `skipped_dup` 但原代码用的是 `skipped`，NameError 直接崩。教训：**补丁后必须跑一次完整 dry-run 或小话题实跑验证**。

### 4. 缺 import glob

加了 `full_files = sorted(glob.glob(...))` 逻辑后漏 import，NameError。教训：**新增逻辑涉及新模块时检查 import 段**。

### 5. batchget 必须 POST

`draft/getdraft`（GET）返回 0 条，是接口本身不对。正确姿势：`draft/batchget` 必须 POST，body `{"offset":0,"count":50,"no_content":0}`。

### 6. newspaper 草稿的图片位置

`article_type=newspic` 的图片存在 `image_info.image_list` 里，不在 `content` 正文里。用正则找 `<img` 数量会得 0——那是找错了位置。草稿本身有效，公众号后台能看到。

## 脚本改动位置

- `pexels_gallery_draft.py`：`process_image()` 加大图降采样；处理阶段产出两版；stdout 输出 `MEDIA:` 标记
- `compress_image.py`：兜底缩分辨率
- `gallery_draft.sh`：成功时 grep `^MEDIA:` 推送

## 通用化

任何「同一素材 → 两版输出（一版进外部系统、一版给用户看）」的流水线都适用这个架构。关键是先搞清外部系统的大小/格式限制，超过限制的版本走另一条不经过该系统的交付路径。
