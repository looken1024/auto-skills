---
name: "douyin-card-pipeline"
description: "抖音流量互助卡片流水线:Pexels抓16:9图,参考截图定位文字框,半透明黑底白字,镜像滤镜噪点去重变体"
---

# douyin-card-pipeline — 抖音流量互助卡片流水线

抖音"流量互助"视频背景图制作：Pexels 抓 16:9 横图 → 分析参考截图文字框位置 → 半透明黑底白字叠字 → 镜像/滤镜/噪点生成去重变体。

## 触发场景

- 用户发来抖音流量互助截图（含"看完点赞评论+关注""众筹一万粉"等文案）要求做同款图
- 用户要求 Pexels 找图、做多图变体避免查重
- 一句话触发："按这个流程来"

## 环境依赖

- Python3 + Pillow + numpy（`pip install pillow numpy`）
- 中文字体：`/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc`（Ubuntu 自带 Noto CJK）
- 无其他第三方依赖

## 核心流程

### 1. Pexels 抓图（fetch）

**关键事实：**
- `www.pexels.com` 被 Cloudflare 挡（403 "Just a moment..."），web_fetch 和 curl 带浏览器 UA 都进不去
- `images.pexels.com` CDN **完全可直连**，只要有 photo id 就能下载
- 搜索方式：用 tavily_search 带 `include_domains:["pexels.com"]` 搜关键词，从结果 URL 提取 `/photos/{id}/`

**直链规则：**
```
https://images.pexels.com/photos/{id}/pexels-photo-{id}.jpeg?auto=compress&cs=tinysrgb&w=1600
```
- 不带 w/h 参数返回原图比例；竖图常见（2:3）
- **16:9 横图裁剪**：`&w=1920&h=1080&fit=crop` → 直接输出 1920×1080

### 2. 参考截图文字框定位（analyze）

用户提供参考图时，**不要用模型猜位置**，用 numpy 程序化分析：

```python
# 中性暗像素检测：黑底文字框是中性色(通道差小)且暗，花朵/天空是彩色
neutral = (abs(R-G) < 18) & (abs(G-B) < 18) & ((R+G+B)/3 < 130)
row_n = neutral.mean(axis=1)   # 行方向找连续段(>3%占比)，间距<12px合并
# 每段内：列方向找中性占比>0.15 的边界 → 归一化坐标 (cx, cy, w, h)
```

- 背景纹理（花朵、枝叶）会干扰梯度法，**中性像素法是实测最稳的**
- 检测出的框通常偏小，加 padding（左右各 8px、上下各 6px）还原真实框
- 结果存 JSON：`[{"cx":..,"cy":..,"w":..,"h":..}]`，坐标均为归一化值（0-1）

**2026-08-29 实测参考布局（4 条字幕分散贴放，非居中堆叠）：**

| 文字 | cx | cy |
|---|---|---|
| 因为我一直刷新推荐页 | 0.195 | 0.182 |
| 看完、点赞、评论+关注 | 0.581 | 0.388 |
| 然后你的作品就能被更多人看到 | 0.509 | 0.678 |
| 众筹一万粉，永不取关 | 0.677 | 0.917 |

### 3. 叠字（render）

样式：**统一样式——半透明黑底圆角框 + 白字**（用户明确要求，不是白底黑字高亮条）：

```python
draw.rounded_rectangle([x0,y0,x0+box_w,y0+box_h], radius=box_h//2, fill=(0,0,0,ALPHA))
draw.text((tx,ty), text, font=font, fill=(255,255,255,255))
```

- 文字宽度用 `draw.textbbox((0,0), text, font=font)` 测量，不用猜
- **参数基线（用户验收版）**：FONT_SIZE=44，BOX_ALPHA=115（0-255，越小越透），pad_x=40，pad_y=24
- 用户调参历史：字号 52→44，透明度 170→115。记住这两个值是"最终满意点"
- 框中心对齐参考坐标 (cx*W, cy*H)，越界保护 `max(10, min(W-box_w-10, x0))`
- 顶部可做轻微压暗渐变（顶部 30% 渐隐），保证亮天空处白字清晰

### 4. 去重变体（variants）

**铁律：先处理背景，再叠文字。** 先翻转再叠字会导致文字镜像变反字。

处理链（按顺序）：
1. 左右镜像 `Image.FLIP_LEFT_RIGHT`
2. 微裁切缩放（2% 边缘裁剪后放大回原尺寸，改变构图指纹，肉眼无感）
3. 滤镜：`ImageEnhance.Contrast/Color/Brightness`
4. 可选色相微转：转 HSV 后 H 通道 +8 左右再合并
5. 像素级高斯噪点：`np.random.normal(0, sigma, shape)`，sigma 2-3
6. 最后叠文字
7. 保存 JPEG quality=88（压缩再次打散指纹）

**变体配方（实测）**：v1 镜像+暖调、v2 镜像+冷调高对比、v3 镜像+色相+饱和、v4 不镜像+微裁切+暖调。

## 脚本

主脚本 `scripts/card_pipeline.py`，子命令：

```
python3 card_pipeline.py fetch <photo_id> [out.jpg]          # Pexels CDN 抓 16:9 图
python3 card_pipeline.py analyze <ref_image> [boxes.json]    # 分析参考截图文字框
python3 card_pipeline.py render <bg.jpg> <boxes.json> [--text "用|分隔"] [--size 44] [--alpha 115]
python3 card_pipeline.py variants <bg.jpg> <boxes.json> [--outdir variants] [--count 4]
```

默认文字（无 --text 时）："因为我一直刷新推荐页|看完、点赞、评论+关注|然后你的作品就能被更多人看到|众筹一万粉，永不取关"

## 坑点备忘

- f-string 里直接写中文引号会 SyntaxError（`{' '` 这类），避免在 f-string 里嵌引号字符
- `ImageEnhance.Sharpness(im).enhance(0)` 是错误用法，别当饱和度用；饱和度用 `Color`
- sed 替换含中文的注释字符串容易不匹配，直接改数字别带中文
- Pexels 图片 id 可能很大（如 31487009），URL 格式不变
- 竖图素材要 16:9 时必须 `fit=crop`，单独 `w=` 参数不会改比例
