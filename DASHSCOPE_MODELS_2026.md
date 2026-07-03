# 阿里云百炼 DashScope 模型清单 (2026)

完整的阿里云百炼可用模型列表，用于 OpenMontage 集成。

## 🎨 图像生成模型（按推荐优先级）

| 优先级 | 模型名称 | 描述 | 推荐场景 |
|-------|---------|------|---------|
| ⭐⭐⭐ | `qwen-image-pro` | 千问图像 Pro 版 | **首选** - 效果最好，综合质量最高 |
| ⭐⭐ | `happyhorse-1.1` | HappyHorse 1.1 | 综合表现突出，平衡性好 |
| ⭐⭐ | `wan2.7-image` | 万相 2.7 图像 | 极致画质和光影，追求细节 |
| ⭐ | `qwen-image` | 千问图像标准版 | 基础版本，速度快 |
| ⭐ | `wanx-v1` | 通义万相 v1 | 传统版本，稳定可靠 |

**推荐策略：**
- 默认使用 `qwen-image-pro`（已设为适配器默认）
- 需要极致画质时使用 `wan2.7-image`
- 追求性价比时使用 `happyhorse-1.1`

## 图像生成模型

### 万相 (Wanxiang)

| 模型名称 | 描述 | 推荐场景 |
|---------|------|---------|
| `wanx-v1` | 通义万相基础版 | 通用图像生成 |
| `wanx2.1-imageedit` | 万相 2.1 图像编辑 | 图像编辑和修改 |
| `wanx-sketch-to-image-v1` | 草图转图像 | 手绘草图转真实图像 |

### 其他图像模型

可能的模型名称（需要通过 API 确认）：
- `flux-*` - Flux 系列模型
- `z-image-*` - Z-Image 模型
- 可灵图像生成模型

## 文本生成模型 (千问 Qwen)

### 千问系列

| 模型名称 | 描述 | 推荐场景 |
|---------|------|---------|
| `qwen-turbo` | 千问 Turbo | 快速响应，低成本 |
| `qwen-plus` | 千问 Plus | 平衡性能和成本 |
| `qwen-max` | 千问 Max | 最强性能 |
| `qwen-vl-plus` | 千问视觉理解 Plus | 图像理解 |
| `qwen-vl-max` | 千问视觉理解 Max | 高级图像理解 |
| `qwen-audio` | 千问音频理解 | 音频理解 |

## 语音合成模型

### 语音生成 (TTS)

使用 `SpeechSynthesizer` 或 `cosyvoice-v1`：

| 模型名称 | 描述 | 推荐场景 |
|---------|------|---------|
| `cosyvoice-v1` | 可思语音 v1 | 高质量语音合成 |
| `sambert-*` | Sambert 系列 | 多语言语音合成 |

## 音频生成模型

### 音乐/音效生成

可能的模型：
- 爱诗 (Aishi) - 音乐生成
- 音频效果生成模型

## 人像驱动模型

### 数字人/虚拟形象

可能的模型：
- 人像驱动模型
- 数字人生成

## 使用建议

### 视频生成优先级

1. **首选**: `wan2.7-t2v-2026-06-12` (最新最强)
2. **备选**: `wanx2.1-t2v-turbo` (快速 + 经济)
3. **高质量**: `wanx2.1-t2v-plus` (质量优先)

### 图像生成优先级

1. **通用**: `wanx-v1`
2. **编辑**: `wanx2.1-imageedit`

### 成本估算 (人民币)

| 资源类型 | 模型 | 单价 (¥) |
|---------|------|---------|
| 图像生成 | wanx-v1 | ~0.08/张 |
| 视频生成 (5秒) | wan2.7 | ~1.50/片段 |
| 视频生成 (5秒) | wanx2.1-turbo | ~1.50/片段 |
| 文本生成 (1K tokens) | qwen-turbo | ~0.002 |
| 语音合成 (1分钟) | cosyvoice | ~0.10 |

## 更新适配器

要使用最新模型，更新 `dashscope_adapter.py` 的默认模型：

```python
# 视频生成默认使用最新模型
response = VideoSynthesis.call(
    model=kwargs.get('model', 'wan2.7-t2v-2026-06-12'),
    prompt=prompt,
    ...
)
```

## 参考文档

- 官方文档: https://help.aliyun.com/zh/model-studio/
- API 参考: https://dashscope.aliyun.com/
- 控制台: https://bailian.console.aliyun.com/
