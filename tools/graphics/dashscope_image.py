"""阿里云百炼 DashScope 图像生成工具（万相-Wanx）.

通过阿里云百炼平台的万相模型生成图像。
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


class DashScopeImage(BaseTool):
    name = "dashscope_image"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "image_generation"
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
    agent_skills = ["flux-best-practices"]

    capabilities = ["text_to_image"]
    supports = {
        "text_to_image": True,
        "chinese_prompts": True,
        "high_quality": True,
        "fast_generation": True,
    }
    best_for = [
        "中文提示词图像生成",
        "国内低延迟访问",
        "高质量图像输出",
    ]
    not_good_for = ["离线生成", "批量生成"]
    fallback_tools = ["flux_image", "google_imagen", "openai_image"]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string", "description": "图像描述文本"},
            "negative_prompt": {"type": "string", "description": "负面提示词"},
            "size": {
                "type": "string",
                "enum": ["1024x1024", "720x1280", "1280x720"],
                "default": "1024x1024",
                "description": "图像尺寸",
            },
            "n": {
                "type": "integer",
                "default": 1,
                "minimum": 1,
                "maximum": 4,
                "description": "生成图像数量",
            },
            "style": {
                "type": "string",
                "enum": ["<auto>", "photography", "portrait", "3d", "anime", "oil", "watercolor", "sketch"],
                "default": "<auto>",
                "description": "图像风格",
            },
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=100, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=3, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = ["prompt", "size", "style"]
    side_effects = ["写入图像文件到 output_path", "调用阿里云 API"]
    user_visible_verification = ["检查生成的图像质量和准确性"]

    def _get_api_key(self) -> str | None:
        return os.environ.get("DASHSCOPE_API_KEY")

    def _get_status(self) -> ToolStatus:
        api_key = self._get_api_key()
        if not api_key:
            return ToolStatus.UNAVAILABLE
        return ToolStatus.AVAILABLE

    def execute(self, params: dict[str, Any]) -> ToolResult:
        """执行图像生成"""
        api_key = self._get_api_key()
        if not api_key:
            return ToolResult(
                success=False,
                error="DASHSCOPE_API_KEY 未配置。请访问 https://bailian.console.aliyun.com/ 获取密钥",
            )

        prompt = params.get("prompt", "")
        negative_prompt = params.get("negative_prompt", "")
        size = params.get("size", "1024x1024")
        n = params.get("n", 1)
        style = params.get("style", "<auto>")
        output_path = params.get("output_path")

        if not output_path:
            return ToolResult(success=False, error="output_path 参数必需")

        try:
            # 获取 Base URL（支持自定义端点）
            base_url = os.environ.get("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com")

            # 尝试使用 compatible-mode（OpenAI 兼容接口）
            if "compatible-mode" in base_url:
                return self._generate_via_compatible_mode(
                    api_key, base_url, prompt, size, n, output_path
                )

            # 否则使用原生 DashScope API
            api_endpoint = f"{base_url}/api/v1/services/aigc/text2image/image-synthesis"

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "X-DashScope-Async": "enable",  # 使用异步模式
            }

            payload = {
                "model": "wanx-v1",
                "input": {
                    "prompt": prompt,
                },
                "parameters": {
                    "size": size,
                    "n": n,
                }
            }

            if negative_prompt:
                payload["input"]["negative_prompt"] = negative_prompt

            if style != "<auto>":
                payload["parameters"]["style"] = style

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
                # 可能是同步返回
                image_url = result.get("output", {}).get("results", [{}])[0].get("url")
                if image_url:
                    return self._download_and_save(image_url, output_path, result)

                return ToolResult(
                    success=False,
                    error=f"未获取到任务ID或图像URL: {result}",
                )

            # 轮询任务状态（异步模式）
            max_wait = 120  # 最多等待2分钟
            poll_interval = 3
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
                    results = status_result.get("output", {}).get("results", [])

                    if not results:
                        return ToolResult(
                            success=False,
                            error="任务完成但未获取到图像",
                        )

                    image_url = results[0].get("url")

                    if not image_url:
                        return ToolResult(
                            success=False,
                            error="未获取到图像URL",
                        )

                    return self._download_and_save(image_url, output_path, status_result)

                elif task_status == "FAILED":
                    error_msg = status_result.get("output", {}).get("message", "未知错误")
                    return ToolResult(
                        success=False,
                        error=f"图像生成失败: {error_msg}",
                    )

            return ToolResult(
                success=False,
                error=f"任务超时（等待了 {elapsed} 秒）",
            )

        except requests.exceptions.Timeout:
            return ToolResult(success=False, error="API 请求超时")
        except Exception as e:
            return ToolResult(success=False, error=f"图像生成失败: {str(e)}")

    def _download_and_save(self, image_url: str, output_path: str, api_result: dict) -> ToolResult:
        """下载并保存图像"""
        try:
            # 下载图像
            image_response = requests.get(image_url, timeout=30)

            if image_response.status_code != 200:
                return ToolResult(
                    success=False,
                    error=f"下载图像失败: {image_response.status_code}",
                )

            # 保存图像
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            output_file.write_bytes(image_response.content)

            return ToolResult(
                success=True,
                data={
                    "image_path": str(output_file),
                    "image_url": image_url,
                    "provider": "dashscope",
                    "model": "wanx-v1",
                    "task_id": api_result.get("output", {}).get("task_id"),
                },
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"保存图像失败: {str(e)}",
            )

    def _generate_via_compatible_mode(
        self, api_key: str, base_url: str, prompt: str, size: str, n: int, output_path: str
    ) -> ToolResult:
        """通过 OpenAI 兼容接口生成图像"""
        try:
            import base64

            # OpenAI 兼容的图像生成端点
            api_endpoint = f"{base_url}/images/generations"

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }

            # 转换尺寸格式（OpenAI 格式）
            size_mapping = {
                "1024x1024": "1024x1024",
                "720x1280": "1024x1792",  # 竖屏
                "1280x720": "1792x1024",  # 横屏
            }
            openai_size = size_mapping.get(size, "1024x1024")

            payload = {
                "model": "wanx-v1",  # 或 "wanx-style-repaint-v1" 用于风格化
                "prompt": prompt,
                "n": n,
                "size": openai_size,
                "response_format": "url",  # 或 "b64_json"
            }

            response = requests.post(
                api_endpoint,
                json=payload,
                headers=headers,
                timeout=60,
            )

            if response.status_code != 200:
                return ToolResult(
                    success=False,
                    error=f"API 请求失败: {response.status_code} - {response.text}",
                )

            result = response.json()
            images = result.get("data", [])

            if not images:
                return ToolResult(
                    success=False,
                    error=f"未获取到图像: {result}",
                )

            # 获取第一张图像
            image_data = images[0]
            image_url = image_data.get("url")
            b64_json = image_data.get("b64_json")

            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)

            if b64_json:
                # Base64 编码的图像
                image_bytes = base64.b64decode(b64_json)
                output_file.write_bytes(image_bytes)
                image_url_final = None
            elif image_url:
                # URL 形式的图像，下载保存
                image_response = requests.get(image_url, timeout=30)
                if image_response.status_code != 200:
                    return ToolResult(
                        success=False,
                        error=f"下载图像失败: {image_response.status_code}",
                    )
                output_file.write_bytes(image_response.content)
                image_url_final = image_url
            else:
                return ToolResult(
                    success=False,
                    error="未获取到图像数据或URL",
                )

            return ToolResult(
                success=True,
                data={
                    "image_path": str(output_file),
                    "image_url": image_url_final,
                    "provider": "dashscope",
                    "model": "wanx-v1",
                    "mode": "compatible",
                },
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Compatible-mode 图像生成失败: {str(e)}",
            )
