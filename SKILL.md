---
name: qwen-image
description: >
  调用阿里云百炼（DashScope/Model Studio）平台上的千问系列及万相系列模型，完成图像生成、
  图像编辑、背景生成、扩图、局部重绘、图像擦除、虚拟模特、创意海报、实例分割等任务。
  当用户涉及以下任何场景时，必须使用此 skill：
  - 调用千问或万相模型生成、编辑图片
  - 百炼平台图像相关 API（背景生成、扩图、虚拟模特、鞋靴模特、海报生成等）
  - 使用 dashscope SDK 或兼容 OpenAI 接口访问 qwen/wanx 模型
  - 文生图、图生图、涂鸦作画、图像擦除、局部重绘、人物分割、图像背景替换
  - 用户提及 qwen-image、wanx、ImageSynthesis、MultiModalConversation 等关键词
---

# Qwen Image Skill

通过运行捆绑的脚本实现所有图像功能。**先检查环境，再运行命令。**

## 第一步：确认地域（必须先问）

**北京和新加坡地域的 API Key 与请求地址完全独立，不可混用，否则鉴权失败。**

如果用户未说明地域，**必须先询问**：

> 您使用的是哪个地域的百炼服务？
> - **中国大陆**（北京）→ `--region cn`
> - **海外 / 新加坡**（默认）→ `--region intl`（可省略）

确认后，在所有命令中统一加上对应的 `--region` 参数。

## 第二步：环境检查

```bash
# 检查 uv 是否可用
command -v uv

# 检查 API Key
echo $DASHSCOPE_API_KEY
```

如果 `uv` 不存在：`pip install uv --break-system-packages`
如果 API Key 为空：提示用户设置对应地域的 API Key：
- 中国大陆：`export DASHSCOPE_API_KEY="sk-xxx"`（百炼北京控制台获取）
- 海外：`export DASHSCOPE_API_KEY="sk-xxx"`（Model Studio 新加坡控制台获取）

## 第三步：脚本路径

```
SKILL_SCRIPT="<skill安装路径>/scripts/run.py"
```

安装位置因环境而异，请根据实际情况替换，例如：
- `~/.claude/skills/bailian-qwen/scripts/run.py`
- `~/.codex/skills/bailian-qwen/scripts/run.py`
- `/path/to/skills/bailian-qwen/scripts/run.py`

---

## 命令速查

> 所有命令均需带 `--region cn`（中国大陆）或 `--region intl`（海外/新加坡，默认值可省略）。
> 以下示例以 `--region cn` 为例，海外用户替换为 `--region intl` 或删除该参数。

### 文生图
```bash
uv run $SKILL_SCRIPT text2img \
  --prompt "冬日雪景中的古典中式庭院，飞檐斗拱" \
  --model qwen-image-2.0-pro \
  --size 2048*2048 \
  --n 1 \
  --region cn \
  --output-dir .
```

### 图像指令编辑（单图）
```bash
uv run $SKILL_SCRIPT edit \
  --prompt "将天空改为星空夜景" \
  --images "https://example.com/photo.jpg" \
  --model qwen-image-edit-max \
  --n 2 \
  --region cn \
  --output-dir .
```

### 多图合成（最多3张图，提示词中引用"图1""图2""图3"）
```bash
uv run $SKILL_SCRIPT edit \
  --prompt "图1中的人物穿着图2的服装，按图3的姿势站立" \
  --images "https://example.com/person.jpg" "https://example.com/outfit.jpg" "https://example.com/pose.jpg" \
  --model qwen-image-edit-max \
  --n 2 \
  --region cn \
  --output-dir .
```

### 商品背景生成（输入须为 RGBA 透明图）
```bash
uv run $SKILL_SCRIPT bg \
  --image "https://example.com/product_rgba.png" \
  --prompt "简约白色大理石桌面，柔和阴影，电商风格" \
  --model-version v3 \
  --n 4 \
  --region cn \
  --output-dir .
```

### 局部重绘（有蒙版：白色区域=重绘）
```bash
uv run $SKILL_SCRIPT inpaint \
  --image "https://example.com/base.jpg" \
  --mask "https://example.com/mask.png" \
  --prompt "一只白色陶瓷兔子" \
  --n 1 \
  --region cn \
  --output-dir .
```

### 图像擦除（无蒙版模式，自动擦除并补全）
```bash
uv run $SKILL_SCRIPT inpaint \
  --image "https://example.com/photo_with_watermark.jpg" \
  --mask "https://example.com/watermark_mask.png" \
  --region cn \
  --output-dir .
```

### 扩图
```bash
uv run $SKILL_SCRIPT outpaint \
  --image "https://example.com/landscape.jpg" \
  --prompt "青山绿水延续场景" \
  --top 200 --bottom 200 --left 300 --right 300 \
  --region cn \
  --output-dir .
```

### 涂鸦/草图转写实
```bash
uv run $SKILL_SCRIPT doodle \
  --image "https://example.com/sketch.png" \
  --prompt "可爱橙色猫咪，写实摄影风格" \
  --strength 0.8 \
  --region cn \
  --output-dir .
```

### 创意海报
```bash
uv run $SKILL_SCRIPT poster \
  --title "双十一狂欢节" \
  --subtitle "全场五折起，限时抢购" \
  --body "11月11日 0点开抢" \
  --style "电商促销风格，红色喜庆，大气热烈" \
  --n 4 \
  --region cn \
  --output-dir .
```

### 人物/前景分割
```bash
uv run $SKILL_SCRIPT segment \
  --image "https://example.com/photo.jpg" \
  --segment-type foreground \
  --region cn \
  --output-dir .
```

### 虚拟模特
```bash
uv run $SKILL_SCRIPT virtualmodel \
  --image "https://example.com/clothing_model.jpg" \
  --bg-prompt "高端商场橱窗，柔和灯光" \
  --model-version v2 \
  --n 4 \
  --region cn \
  --output-dir .
```

---

## 常用参数参考

| 参数 | 说明 |
|------|------|
| `--region cn` | 中国大陆（北京），请求地址：`dashscope.aliyuncs.com` |
| `--region intl` | 海外/新加坡（**默认值**），请求地址：`dashscope-intl.aliyuncs.com` |
| `--n` | 生成数量（1-6） |
| `--output-dir` | 保存目录（默认当前目录） |
| `--api-key` | API Key（可用环境变量代替）|
| `--no-extend` | 禁用提示词自动扩写 |

## 常用 size 值

### qwen-image-2.0-pro / qwen-image-2.0（总像素需在 512×512～2048×2048 之间）

| size | 比例 |
|------|------|
| `2048*2048`（默认）| 1:1 |
| `2688*1536` | 16:9 横版 |
| `1536*2688` | 9:16 竖版 |
| `2368*1728` | 4:3 |
| `1728*2368` | 3:4 |

### qwen-image-max / qwen-image-plus / qwen-image（固定可选值）

| size | 比例 |
|------|------|
| `1328*1328`（默认）| 1:1 |
| `1664*928` | 16:9 横版 |
| `928*1664` | 9:16 竖版 |
| `1472*1104` | 4:3 |
| `1104*1472` | 3:4 |

## 注意事项

- 生成图片 URL **有效期 24 小时**，脚本已自动下载保存到本地
- 虚拟模特（`virtualmodel`）目前仅免费体验，额度用完后不可调用，可用 `edit` 子命令替代
- 商品背景生成（`bg`）需要 **RGBA（含透明通道）** 的 PNG 图，可先用 `segment` 分割前景再合成
- 万相系列（bg / inpaint / outpaint / doodle / poster / segment / virtualmodel）均为异步接口，脚本自动轮询

## 故障排查

| 错误 | 解决方案 |
|------|---------|
| `No API key provided` | `export DASHSCOPE_API_KEY="sk-xxx"` |
| `Model not exist` | 检查模型名拼写；bg 接口 model 固定为 `wanx-background-generation-v2` |
| `Image format must be RGBA` | bg 命令输入图需 RGBA 格式，请先转换 |
| `quota/permission/403` | API Key 无对应模型权限，或免费额度耗尽 |
| `Task timeout` | 增加轮询等待时间或重试 |
