#!/usr/bin/env python3
"""
测试阿里云千问图像生成模型

对比 Qwen-Image Pro, HappyHorse 1.1, Wan 2.7
"""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent))

from lib.provider_adapters import DashScopeAdapter


def test_image_models():
    """测试不同图像模型"""

    print("=" * 70)
    print("🎨 阿里云图像生成模型对比测试")
    print("=" * 70)

    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        print("❌ DASHSCOPE_API_KEY 未配置")
        return False

    adapter = DashScopeAdapter(api_key=api_key)

    if not adapter.is_available():
        print("❌ 适配器不可用")
        return False

    print(f"✅ 适配器就绪\n")

    output_dir = Path("projects") / "image-model-comparison"
    output_dir.mkdir(parents=True, exist_ok=True)

    # 测试场景
    test_prompt = "一只可爱的熊猫坐在竹林中，阳光透过竹叶洒下金色的光芒，高清摄影，细节丰富"

    # 测试模型列表（按推荐优先级）
    test_models = [
        {
            "name": "Qwen-Image Pro",
            "model": "qwen-image-pro",
            "desc": "效果最好（首选）"
        },
        {
            "name": "HappyHorse 1.1",
            "model": "happyhorse-1.1",
            "desc": "综合表现突出"
        },
        {
            "name": "Wan 2.7",
            "model": "wan2.7",
            "desc": "极致画质和光影"
        },
    ]

    results = []

    for i, test_case in enumerate(test_models, 1):
        print(f"{'=' * 70}")
        print(f"测试 {i}/{len(test_models)}: {test_case['name']}")
        print(f"{'=' * 70}")
        print(f"模型: {test_case['model']}")
        print(f"特点: {test_case['desc']}")
        print(f"提示词: {test_prompt}")
        print("⏳ 生成中...\n")

        output_path = output_dir / f"{test_case['model'].replace('/', '_')}.png"

        result = adapter.generate_image(
            prompt=test_prompt,
            size="1024x1024",
            output_path=str(output_path),
            model=test_case['model']
        )

        if result.success:
            print(f"✅ 成功!")
            print(f"   路径: {result.data['image_path']}")
            print(f"   成本: ${result.cost:.4f} (约 ¥{result.cost * 7.2:.2f})")
            results.append({
                "name": test_case['name'],
                "model": test_case['model'],
                "success": True,
                "cost": result.cost,
                "path": result.data['image_path']
            })
        else:
            print(f"❌ 失败: {result.error}")
            results.append({
                "name": test_case['name'],
                "model": test_case['model'],
                "success": False,
                "error": result.error
            })

        print()

    # 总结
    print("=" * 70)
    print("📊 测试结果汇总")
    print("=" * 70)

    success_count = sum(1 for r in results if r['success'])
    total_cost = sum(r.get('cost', 0) for r in results if r['success'])

    print(f"\n成功率: {success_count}/{len(results)}")
    print(f"总成本: ${total_cost:.4f} (约 ¥{total_cost * 7.2:.2f})")

    print("\n详细结果:")
    for r in results:
        status = "✅" if r['success'] else "❌"
        print(f"\n{status} {r['name']}")
        print(f"   模型: {r['model']}")
        if r['success']:
            print(f"   成本: ${r['cost']:.4f}")
            print(f"   文件: {r['path']}")
        else:
            print(f"   错误: {r['error']}")

    if success_count > 0:
        print(f"\n\n📁 生成的图片位于: {output_dir}/")
        print("   你可以对比不同模型的画质、光影、细节表现")
        print("\n推荐优先级：")
        print("  1. Qwen-Image Pro - 效果最好")
        print("  2. HappyHorse 1.1 - 综合平衡")
        print("  3. Wan 2.7 - 极致画质")

    return True


def main():
    """主函数"""

    print("\n⚠️  注意:")
    print("  - 将生成 3 张图片进行对比")
    print("  - 预计成本约 ¥0.24-0.3")
    print("\n确认继续? (y/n): ", end="")

    try:
        choice = input().strip().lower()
        if choice != 'y':
            print("\n操作取消")
            return
    except (KeyboardInterrupt, EOFError):
        print("\n\n操作取消")
        return

    test_image_models()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n操作被中断")
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
