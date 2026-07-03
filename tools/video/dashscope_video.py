"""阿里云百炼 DashScope 视频生成工具.

通过阿里云百炼平台的视频生成能力生成视频。
"""

from __future__ import annotations

import os
import time
import requests
from pathlib import Path
from typing import Any

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    RetryPolicy,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)


class DashScopeVideo(BaseTool):
    name = "dashscope_video"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "video_generation"
    provider = "dashscope"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = []
    install_instructions = (
        "配置阿里云百炼 API 密钥:\n"
        "  1. 访问 https://bailian.console.aliyun.com/\n"
        "  2. 创建 API Key\n"
        "  3. 设置环境变量: DASHSCOPE_API_KEY=你的密钥"
    )
    agent_skills = ["ai-video-gen"]

    capabilities = ["text_to_video", "image_to_video"]
    supports = {
        "text_to_video": True,
        "image_to_video": True,
        "chinese_prompts": True,
        "async_generation": True,
    }
    best_for = [
        "中文提示词视频生成",
        "国内低延迟访问",
        "支持异步任务查询",
    ]
    not_good_for = ["离线生成", "实时生成"]
    fallback_tools = ["kling_video", "minimax_video"]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string", "description": "视频描述文本"},
            "operation": {
                "type": "string",
                "enum": ["text_to_video", "image_to_video"],
                "default": "text_to_video",
            },
            "duration": {
                "type": "integer",
                "default": 5,
                "description": "视频时长（秒）",
            },
            "aspect_ratio": {
                "type": "string",
                "enum": ["16:9", "9:16", "1:1"],
                "default": "16:9",
            },
            "image_url": {
                "type": "string",
                "description": "参考图像URL（image_to_video模式）",
            },
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=500, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=3, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = ["prompt", "operation", "duration"]
    side_effects = ["写入视频文件到 output_path", "调用阿里云 API"]
    user_visible_verification = ["检查生成的视频质量和流畅度"]

    def _get_api_key(self) -> str | None:
        return os.environ.get("DASHSCOPE_API_KEY")

    def _get_status(self) -> ToolStatus:
        api_key = self._get_api_key()
        if not api_key:
            return ToolStatus.UNAVAILABLE
        return ToolStatus.AVAILABLE

    def execute(self, params: dict[str, Any]) -> ToolResult:
        """执行视频生成"""
        api_key = self._get_api_key()
        if not api_key:
            return ToolResult(
                success=False,
                error="DASHSCOPE_API_KEY 未配置。请访问 https://bailian.console.aliyun.com/ 获取密钥",
            )

        prompt = params.get("prompt", "")
        operation = params.get("operation", "text_to_video")
        duration = params.get("duration", 5)
        aspect_ratio = params.get("aspect_ratio", "16:9")
        output_path = params.get("output_path")
        image_url = params.get("image_url")

        if not output_path:
            return ToolResult(success=False, error="output_path 参数必需")

        try:
            # 阿里云 DashScope API 调用
            # 注意：这是示例实现，实际 API 端点和参数需要根据官方文档调整
            api_endpoint = "https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/generation"

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }

            payload = {
                "model": "wanx-video-v1",  # 根据实际可用模型调整
                "input": {
                    "prompt": prompt,
                    "duration": duration,
                },
                "parameters": {
                    "aspect_ratio": aspect_ratio,
                }
            }

            if operation == "image_to_video" and image_url:
                payload["input"]["image_url"] = image_url

            # 提交任务
            response = requests.post(api_endpoint, json=payload, headers=headers, timeout=30)

            if response.status_code != 200:
                return ToolResult(
                    success=False,
                    error=f"API 请求失败: {response.status_code} - {response.text}",
                )

            result = response.json()
            task_id = result.get("output", {}).get("task_id")

            if not task_id:
                return ToolResult(
                    success=False,
                    error=f"未获取到任务ID: {result}",
                )

            # 轮询任务状态
            max_wait = 300  # 最多等待5分钟
            poll_interval = 5
            elapsed = 0

            status_endpoint = f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"

            while elapsed < max_wait:
                time.sleep(poll_interval)
                elapsed += poll_interval

                status_response = requests.get(status_endpoint, headers=headers, timeout=30)

                if status_response.status_code != 200:
                    return ToolResult(
                        success=False,
                        error=f"查询任务状态失败: {status_response.status_code}",
                    )

                status_result = status_response.json()
                task_status = status_result.get("output", {}).get("task_status")

                if task_status == "SUCCEEDED":
                    video_url = status_result.get("output", {}).get("video_url")

                    if not video_url:
                        return ToolResult(
                            success=False,
                            error="任务完成但未获取到视频URL",
                        )

                    # 下载视频
                    video_response = requests.get(video_url, timeout=60)

                    if video_response.status_code != 200:
                        return ToolResult(
                            success=False,
                            error=f"下载视频失败: {video_response.status_code}",
                        )

                    # 保存视频
                    output_file = Path(output_path)
                    output_file.parent.mkdir(parents=True, exist_ok=True)
                    output_file.write_bytes(video_response.content)

                    return ToolResult(
                        success=True,
                        data={
                            "video_path": str(output_file),
                            "task_id": task_id,
                            "provider": "dashscope",
                            "duration": duration,
                        },
                    )

                elif task_status == "FAILED":
                    error_msg = status_result.get("output", {}).get("message", "未知错误")
                    return ToolResult(
                        success=False,
                        error=f"视频生成失败: {error_msg}",
                    )

            return ToolResult(
                success=False,
                error=f"任务超时（等待了 {elapsed} 秒）",
            )

        except requests.exceptions.Timeout:
            return ToolResult(success=False, error="API 请求超时")
        except Exception as e:
            return ToolResult(success=False, error=f"视频生成失败: {str(e)}")
