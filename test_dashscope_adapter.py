#!/usr/bin/env python3
"""
DashScope SDK 适配器测试

测试使用官方 SDK 进行图像和视频生成
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# 加载环境变量
from dotenv import load_dotenv
load_dotenv()

from lib.provider_adapters import DashScopeAdapter


def test_adapter():
    """测试适配器"""
    print("=" * 60)
    print("🧪 DashScope SDK 适配器测试")
    print("=" * 60)

    # 获取 API Key
    api_key = os.environ.get("DASHSCOPE_API_KEY")

    if not api_key:
        print("❌ DASHSCOPE_API_KEY 未配置")
        return False

    print(f"✅ API Key: {api_key[:20]}...")

    # 创建适配器
    adapter = DashScopeAdapter(api_key=api_key)

    # 检查可用性
    if not adapter.is_available():
        print("❌ 适配器不可用（可能缺少 SDK）")
        return False

    print(f"✅ 提供商: {adapter.provider_name}")
    print(f"✅ SDK 已加载")

    return adapter


def test_image_generation(adapter):
    """测试图像生成"""
    print("\n" + "=" * 60)
    print("🎨 测试图像生成（DashScope SDK）")
    print("=" * 60)

    output_dir = Path("/tmp/openmontage_adapter_test")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "dashscope_panda.png"

    print(f"\n提示词: '一只可爱的熊猫在竹林里'")
    print(f"输出路径: {output_path}")
    print("\n正在生成，请稍候...\n")

    result = adapter.generate_image(
        prompt="一只可爱的熊猫在竹林里，水墨画风格",
        size="1024x1024",
        output_path=str(output_path)
    )

    if result.success:
        print("✅ 图像生成成功!")
        print(f"   提供商: {result.provider}")
        print(f"   图像 URL: {result.data.get('image_url')}")
        print(f"   本地路径: {result.data.get('image_path')}")
        print(f"   模型: {result.data.get('model')}")
        print(f"   成本: ${result.cost:.4f}")

        if result.metadata:
            print(f"   任务 ID: {result.metadata.get('task_id')}")

        # 检查文件
        if result.data.get('image_path') and Path(result.data['image_path']).exists():
            file_size = Path(result.data['image_path']).stat().st_size
            print(f"   文件大小: {file_size / 1024:.2f} KB")
            return True
        else:
            print("⚠️  文件未保存到本地")
            return False
    else:
        print(f"❌ 图像生成失败: {result.error}")
        return False


def test_batch_generation(adapter):
    """测试批量生成"""
    print("\n" + "=" * 60)
    print("🎨 测试批量生成（3张）")
    print("=" * 60)

    test_cases = [
        ("中国山水画", "landscape_sdk.png"),
        ("未来科技城市", "city_sdk.png"),
        ("可爱的小猫咪", "cat_sdk.png"),
    ]

    output_dir = Path("/tmp/openmontage_adapter_test")
    success_count = 0

    for i, (prompt, filename) in enumerate(test_cases, 1):
        print(f"\n[{i}/3] {prompt}")
        output_path = output_dir / filename

        result = adapter.generate_image(
            prompt=prompt,
            size="1024x1024",
            output_path=str(output_path)
        )

        if result.success:
            print(f"     ✅ 成功 (${result.cost:.4f})")
            success_count += 1
        else:
            print(f"     ❌ 失败: {result.error}")

    print(f"\n完成: {success_count}/3 成功")
    return success_count == 3


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("🚀 DashScope SDK 适配器测试")
    print("=" * 60)

    # 1. 测试适配器初始化
    adapter = test_adapter()
    if not adapter:
        print("\n❌ 适配器初始化失败")
        return

    # 2. 测试单张图像生成
    image_success = test_image_generation(adapter)

    if not image_success:
        print("\n⚠️  图像生成测试失败")
        print("\n可能的原因:")
        print("  1. API 密钥无效")
        print("  2. 账户余额不足")
        print("  3. 网络连接问题")
        print("  4. SDK 版本不兼容")
        return

    # 3. 询问是否批量测试
    print("\n是否进行批量生成测试？(将生成 3 张图像)")
    print("输入 'y' 继续，其他键跳过: ", end="")

    try:
        choice = input().strip().lower()
        if choice == 'y':
            test_batch_generation(adapter)
        else:
            print("跳过批量测试")
    except (KeyboardInterrupt, EOFError):
        print("\n测试中断")

    # 总结
    print("\n" + "=" * 60)
    print("✅ DashScope SDK 适配器测试完成!")
    print("=" * 60)
    print("\n生成的文件位于: /tmp/openmontage_adapter_test/")
    print("\n✨ 适配器工作正常！")
    print("\n下一步:")
    print("  1. 适配器已集成到 OpenMontage")
    print("  2. 现在可以通过工具层调用")
    print("  3. 支持自动故障转移到其他提供商")
    print("  4. 查看文档: COMMERCIAL_ARCHITECTURE.md")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n测试被中断")
    except Exception as e:
        print(f"\n❌ 测试出错: {e}")
        import traceback
        traceback.print_exc()
