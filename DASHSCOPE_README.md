# 阿里云百炼集成 - 快速指南

## ✅ 已集成

### 图像生成（默认：Qwen-Image Pro）

```python
from lib.provider_adapters import DashScopeAdapter

adapter = DashScopeAdapter(api_key="your_api_key")

# 自动使用 qwen-image-pro（效果最好）
result = adapter.generate_image(
    prompt="一只可爱的熊猫在竹林中",
    size="1024x1024",
    output_path="panda.png"
)
```

**推荐模型优先级：**
1. `qwen-image-pro` - 效果最好（默认）
2. `happyhorse-1.1` - 综合平衡
3. `wan2.7-image` - 极致画质

### 视频生成（默认：Wan 2.7）

```python
# 文本转视频（支持最长 15 秒）
result = adapter.generate_video(
    prompt="熊猫在竹林中玩耍",
    duration=5,
    aspect_ratio="16:9",
    output_path="panda.mp4"
)

# 可灵多镜头
result = adapter.generate_video(
    model="kling/kling-v3-video-generation",
    multi_prompt=[
        {"index": 1, "prompt": "场景1", "duration": 5},
        {"index": 2, "prompt": "场景2", "duration": 5}
    ]
)
```

## 🧪 测试

```bash
# 测试图像生成（对比 3 个模型）
python test_qwen_image.py

# 测试视频生成（15秒演示）
python create_video_demo.py
```

## 📚 文档

- [DASHSCOPE_MODELS_2026.md](DASHSCOPE_MODELS_2026.md) - 完整模型清单
- [INTEGRATION_SUMMARY.md](INTEGRATION_SUMMARY.md) - 详细集成说明

## 🔑 配置

```bash
# .env
DASHSCOPE_API_KEY=sk-your-api-key
```

## 💰 成本参考

- 图像：¥0.08/张
- 视频：¥1.5/5秒

---

**核心文件:**
- `lib/provider_adapters/dashscope_adapter.py` - 适配器实现
- `test_qwen_image.py` - 图像测试
- `create_video_demo.py` - 视频测试
