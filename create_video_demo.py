#!/usr/bin/env python3
"""
OpenMontage 15秒宣传视频 - 使用阿里云百炼视频生成

直接使用 DashScope SDK 生成运动视频片段
"""

import sys
from pathlib import Path
from dotenv import load_dotenv
import json

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent))

from lib.provider_adapters import DashScopeAdapter


def create_video_with_motion():
    """使用阿里云百炼生成真实运动视频"""

    print("=" * 70)
    print("🎬 OpenMontage 15秒宣传视频 - 运动视频版")
    print("=" * 70)
    print("\n使用阿里云百炼视频生成 SDK")
    print("每个片段约需 1-3 分钟生成时间\n")

    # 项目配置
    project_name = "openmontage-demo-video-15s"
    project_dir = Path("projects") / project_name
    project_dir.mkdir(parents=True, exist_ok=True)

    video_dir = project_dir / "assets" / "video"
    video_dir.mkdir(parents=True, exist_ok=True)

    print(f"📁 项目目录: {project_dir}\n")

    # 3个视频片段，每个5秒
    video_scenes = [
        {
            "id": 1,
            "duration": 5,
            "prompt": "A futuristic AI studio with holographic screens showing video timelines, blue tech atmosphere, cinematic camera movement, professional lighting",
            "prompt_cn": "未来感的AI工作室，全息投影屏幕显示视频时间线，蓝色科技氛围，电影级镜头运动，专业灯光",
            "aspect_ratio": "16:9"
        },
        {
            "id": 2,
            "duration": 5,
            "prompt": "Creative person working on laptop with video editing interface on screen, warm studio lighting, smooth camera dolly shot",
            "prompt_cn": "创意工作者使用笔记本电脑编辑视频，屏幕显示编辑界面，温暖工作室灯光，平滑推轨镜头",
            "aspect_ratio": "16:9"
        },
        {
            "id": 3,
            "duration": 5,
            "prompt": "Wall of video thumbnails showcasing various video projects, cinematic quality, slow camera pan",
            "prompt_cn": "视频作品展示墙，多个缩略图展示不同风格的视频项目，电影级质感，缓慢横摇镜头",
            "aspect_ratio": "16:9"
        }
    ]

    print(f"📹 将生成 {len(video_scenes)} 个运动视频片段")
    print("=" * 70)

    # 创建适配器
    import os
    api_key = os.getenv("DASHSCOPE_API_KEY")

    if not api_key:
        print("❌ 错误: DASHSCOPE_API_KEY 未配置")
        return False

    adapter = DashScopeAdapter(api_key=api_key)

    if not adapter.is_available():
        print("❌ 错误: DashScope 适配器不可用")
        return False

    print(f"✅ 使用提供商: {adapter.provider_name}\n")

    # 生成视频片段
    generated_videos = []
    total_cost = 0.0

    for scene in video_scenes:
        print(f"视频片段 {scene['id']}/{len(video_scenes)}")
        print(f"  提示词(中文): {scene['prompt_cn']}")
        print(f"  时长: {scene['duration']}秒")
        print(f"  宽高比: {scene['aspect_ratio']}")

        output_path = video_dir / f"clip_{scene['id']}.mp4"

        print(f"  ⏳ 生成中（预计 1-3 分钟）...")

        # 使用中文提示词（阿里云对中文支持更好）
        result = adapter.generate_video(
            prompt=scene['prompt_cn'],
            duration=scene['duration'],
            aspect_ratio=scene['aspect_ratio'],
            output_path=str(output_path)
        )

        if result.success:
            print(f"  ✅ 成功!")
            print(f"     路径: {result.data['video_path']}")
            print(f"     时长: {result.data.get('duration')}秒")
            print(f"     成本: ${result.cost:.4f} (约 ¥{result.cost * 7.2:.2f})")

            scene['video_path'] = result.data['video_path']
            scene['video_url'] = result.data.get('video_url')
            generated_videos.append(scene)
            total_cost += result.cost
        else:
            print(f"  ❌ 失败: {result.error}")
            print(f"  建议: 检查账户余额和API配额")
            # 继续尝试下一个
            continue

        print()

    if not generated_videos:
        print("❌ 没有成功生成任何视频片段")
        return False

    print("=" * 70)
    print(f"✅ 成功生成 {len(generated_videos)}/{len(video_scenes)} 个视频片段")
    print(f"💰 总成本: ${total_cost:.4f} (约 ¥{total_cost * 7.2:.2f})")

    # 保存场景规划
    scene_plan = {
        "title": "OpenMontage 15秒宣传视频（运动版）",
        "duration": sum(s['duration'] for s in generated_videos),
        "clips": generated_videos,
        "total_cost": total_cost,
        "provider": "dashscope"
    }

    plan_path = project_dir / "video_plan.json"
    with open(plan_path, 'w', encoding='utf-8') as f:
        json.dump(scene_plan, f, indent=2, ensure_ascii=False)

    print(f"📄 视频规划已保存: {plan_path}")

    return True, generated_videos


def concat_videos(video_clips, output_path):
    """使用 FFmpeg 连接视频片段"""

    print("\n" + "=" * 70)
    print("🎞️  合成最终视频")
    print("=" * 70)

    import subprocess

    # 创建 concat 列表文件
    concat_file = Path(output_path).parent / "concat_list.txt"

    with open(concat_file, 'w') as f:
        for clip in video_clips:
            if 'video_path' in clip:
                f.write(f"file '{Path(clip['video_path']).absolute()}'\n")

    print(f"\n合成 {len(video_clips)} 个视频片段...")
    print(f"输出: {output_path}")

    cmd = [
        'ffmpeg', '-y',
        '-f', 'concat',
        '-safe', '0',
        '-i', str(concat_file),
        '-c', 'copy',
        str(output_path)
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode == 0 and Path(output_path).exists():
            file_size = Path(output_path).stat().st_size / (1024 * 1024)
            print(f"\n✅ 视频合成成功!")
            print(f"   文件: {output_path}")
            print(f"   大小: {file_size:.2f} MB")

            # 删除临时文件
            concat_file.unlink()

            return True
        else:
            print(f"\n❌ FFmpeg 失败: {result.stderr[:500]}")
            return False

    except Exception as e:
        print(f"\n❌ 合成失败: {e}")
        return False


def main():
    """主函数"""

    print("\n" + "=" * 70)
    print("OpenMontage 演示 - 使用阿里云百炼生成运动视频")
    print("=" * 70)
    print("\n⚠️  注意:")
    print("  - 每个5秒视频片段需要 1-3 分钟生成时间")
    print("  - 3个片段总计约需 3-9 分钟")
    print("  - 成本约 ¥3.6-5.4 (3个片段)")
    print("\n确认继续? (y/n): ", end="")

    try:
        choice = input().strip().lower()
        if choice != 'y':
            print("\n操作取消")
            return
    except (KeyboardInterrupt, EOFError):
        print("\n\n操作取消")
        return

    # 1. 生成视频片段
    result = create_video_with_motion()

    if not result:
        print("\n❌ 视频生成失败")
        return

    success, video_clips = result

    if not video_clips:
        print("\n❌ 没有可用的视频片段进行合成")
        return

    # 2. 合成最终视频
    project_dir = Path("projects") / "openmontage-demo-video-15s"
    output_dir = project_dir / "renders"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "final_demo.mp4"

    concat_success = concat_videos(video_clips, output_path)

    if concat_success:
        print("\n" + "=" * 70)
        print("🎉 完成!")
        print("=" * 70)
        print(f"\n最终视频: {output_path}")
        print("\n你现在拥有一个使用 AI 生成的 15 秒宣传视频!")
        print("完全使用阿里云百炼生成 ✨")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n操作被中断")
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
