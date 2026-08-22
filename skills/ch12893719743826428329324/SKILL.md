# ✨ API Image

通过 API 接口生成图片，**不绑定任何中转服务商**，支持 **Gemini**、**OpenAI DALL-E**、**最新的GPT-Image-2** 模型，开箱即用。

## ✨ 核心特性

| 特性 | 说明 |
|------|------|
| 🌐 **多模型支持** | 自动识别模型家族，支持 Gemini、DALL-E、GPT-Image等 |
| 🖼️ **参考图支持** | Gemini 天然支持多张参考图输入，适合图片编辑、风格融合 |
| 📐 **智能参数映射** | 自动将宽高比映射为对应模型支持的尺寸
| 🔧 **开箱即用** | 安装后用户只需要把 API 信息发给智能体，自动完成配置 |
| 🛡️ **安全通用** | 技能不内置任何 API Key、服务地址、模型名称，完全由用户配置 |
| ⏱️ **合理超时** | 默认 5 分钟超时，适配图片生成的长时间等待 |
| 🎯 **错误友好** | 提前配置检查、清晰错误提示，避免不必要的请求扣费 |

## 📖 支持的模型

| 模型家族 | 识别关键字 | 支持特性 |
|---------|-----------|---------|
| **Gemini** | `gemini` | 参考图、温度参数、宽高比、分辨率 (512/1K/2K/4K) |
| **DALL-E** | `dall-e` / `dalle` | 尺寸 (1024x1024 / 1792x1024 / 1024x1792)、画质 (standard/hd)、风格 (vivid/natural) |
| **GPT-Image** | `gpt-image` | 尺寸 (1024x1024 / 1536x1024 / 1024x1536)、画质 (low/medium/high/auto)、背景 (transparent/opaque/auto)、多图 (1-10张) |
| **Banana** | `banana` | 标准 OpenAI 兼容参数 |

## 📖 安装使用

### 🚀 安装后第一步

**安装完成后，将以下信息发给你的智能体即可完成配置**：
```
- API Key: 你的令牌密钥
- Base URL: 你的中转站请求地址
- Model: 模型名称（请根据中转站命名方式填写）
- API Type: google  # 可选值: google, openai（也可以不填，自动识别）
```
智能体帮你完成配置，之后会生成一张测试图片验证接口连通性。

### ⌨️ 命令行使用（手动）

```bash
# 检查配置
./skills/api-image/scripts/api_image.py check

# 纯文本生成（通用）
./skills/api-image/scripts/api_image.py generate "你的提示词" -o output.png -r 16:9

# Gemini 专用参数
./skills/api-image/scripts/api_image.py generate "你的提示词" -o output.png -r 16:9 -R 2K -t 0.9

# DALL-E 专用参数
./skills/api-image/scripts/api_image.py generate "你的提示词" -o output.png -r 16:9 -q hd --style vivid

# GPT-Image 专用参数
./skills/api-image/scripts/api_image.py generate "你的提示词" -o output.png -r 16:9 -q high --background transparent -n 4

# 参考图生成（仅 Gemini）
./skills/api-image/scripts/api_image.py reference ref1.png ref2.png -p "把这两张图融合成一张新图" -o output.png
```

### ⚙️ 参数说明

#### 通用参数

| 参数 | 说明 |
|------|------|
| `-p/--prompt` | 提示词/编辑指令 **(参考图生成必填)** |
| `-o/--output` | 输出图片文件名/路径 (默认 `output.jpg`)，多图时支持 `{i}` 占位符 |
| `-r/--aspect-ratio` | 图片宽高比，例如 `1:1`/`16:9`/`9:16`/`4:3`/`3:4` |
| `--api-type` | API 类型 (`google`/`openai`)，默认从模型自动识别 |
| `--base-url` | API 基础地址，默认从配置读取 |
| `--model` | 模型名称，默认从配置读取 |
| `--api-key` | API Key，默认从配置读取 |
| `--timeout` | 请求超时（秒，默认 `300`） |

#### Gemini 专用

| 参数 | 说明 |
|------|------|
| `-t/--temperature` | 温度 (0-1，默认 `0.9`) |
| `-R/--resolution` | 图片分辨率，可选 `512`/`1K`/`2K`/`4K` |

#### OpenAI DALL-E 专用

| 参数 | 说明 |
|------|------|
| `-s/--size` | 图片尺寸，例如 `1024x1024`/`1792x1024` (优先使用 `--aspect-ratio`) |
| `-q/--quality` | 画质，可选 `standard`/`hd` |
| `--style` | 风格，可选 `vivid` (鲜艳)/`natural` (自然) |

#### GPT-Image 专用

| 参数 | 说明 |
|------|------|
| `-s/--size` | 图片尺寸，例如 `1024x1024`/`1536x1024` (优先使用 `--aspect-ratio`) |
| `-q/--quality` | 画质，可选 `low`/`medium`/`high`/`auto` |
| `--background` | 背景，可选 `transparent`/`opaque`/`auto` |
| `--moderation` | 内容审核，可选 `auto`/`low` |
| `-n/--number` | 生成图片数量，支持 1-10 张 |

---

## 🔧 技术实现细节（供开发者参考）

### 模型识别逻辑

- **Gemini**: 模型名包含 `gemini` → 使用 Google 协议，标准 Gemini 格式
- **DALL-E**: 模型名包含 `dall-e` 或 `dalle` → 使用 OpenAI 协议，DALL-E 特有参数
- **GPT-Image**: 模型名包含 `gpt-image` → 使用 OpenAI 协议，GPT-Image 特有参数
- **Banana**: 模型名包含 `banana` → 使用 OpenAI 协议，标准参数

### Gemini imageConfig

Gemini 支持通过 `image_config` 设置：
- `aspect_ratio`: `1:1`, `1:4`, `1:8`, `2:3`, `3:2`, `3:4`, `4:1`, `4:3`, `4:5`, `5:4`, `8:1`, `9:16`, `16:9`, `21:9`
- `image_size`: `512`, `1K`, `2K`, `4K`

### 宽高比自动映射

**DALL-E / Banana**:
- `1:1` → `1024x1024`
- `16:9` / `4:3` → `1792x1024`
- `9:16` / `3:4` → `1024x1792`

**GPT-Image**:
- `1:1` → `1024x1024`
- `16:9` / `4:3` → `1536x1024`
- `9:16` / `3:4` → `1024x1536`

### 响应解析

**Google 协议**: `data.candidates[0].content.parts[0].inlineData.data`

**OpenAI 协议**: 
- 优先: `data.data[0].b64_json`
- 备选: `data.data[0].url` 或 `data.images[0].url`

### 多图生成策略

- **DALL-E**: 强制 `n=1`（官方限制）
- **GPT-Image**: 支持 `n=1-10`
- **Gemini**: 单次请求只返回一张

---

技能做好了通用化设计，不管你用哪个中转，只要支持标准协议就能用，是你图片生成的通用利器 🎉
