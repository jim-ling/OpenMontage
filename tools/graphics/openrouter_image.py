"""OpenRouter 统一 AI 模型网关 - 图像生成.

通过 OpenRouter API 访问多个图像生成模型。
"""

from __future__ import annotations

import os
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


class OpenRouterImage(BaseTool):
    name = "openrouter_image"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "image_generation"
    provider = "openrouter"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = []
    install_instructions = (
        "配置 OpenRouter API 密钥:\n"
        "  1. 访问 https://openrouter.ai/keys\n"
        "  2. 创建 API Key\n"
        "  3. 设置环境变量: OPENROUTER_API_KEY=你的密钥"
    )
    agent_skills = ["flux-best-practices"]

    capabilities = ["text_to_image"]
    supports = {
        "text_to_image": True,
        "multiple_models": True,
        "unified_api": True,
    }
    best_for = [
        "统一访问多个 AI 模型",
        "自动模型选择和故障转移",
        "按使用量付费",
    ]
    not_good_for = ["离线生成", "需要特定模型特性"]
    fallback_tools = ["flux_image", "openai_image"]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string", "description": "图像描述文本"},
            "model": {
                "type": "string",
                "default": "stability-ai/stable-diffusion-xl",
                "description": "模型名称（如 stability-ai/stable-diffusion-xl, black-forest-labs/flux-schnell 等）",
            },
            "size": {
                "type": "string",
                "enum": ["256x256", "512x512", "1024x1024", "1792x1024", "1024x1792"],
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
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=100, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=3, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = ["prompt", "model", "size"]
    side_effects = ["写入图像文件到 output_path", "调用 OpenRouter API"]
    user_visible_verification = ["检查生成的图像质量"]

    def _get_api_key(self) -> str | None:
        return os.environ.get("OPENROUTER_API_KEY")

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
                error="OPENROUTER_API_KEY 未配置。请访问 https://openrouter.ai/keys 获取密钥",
            )

        prompt = params.get("prompt", "")
        model = params.get("model", "stability-ai/stable-diffusion-xl")
        size = params.get("size", "1024x1024")
        n = params.get("n", 1)
        output_path = params.get("output_path")

        if not output_path:
            return ToolResult(success=False, error="output_path 参数必需")

        try:
            # OpenRouter 图像生成 API
            # 注意：OpenRouter 主要是文本模型网关，图像生成支持可能有限
            # 这里使用 OpenAI 兼容的接口格式
            api_endpoint = "https://openrouter.ai/api/v1/images/generations"

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://openmontage.ai",  # 可选：你的网站
                "X-Title": "OpenMontage",  # 可选：应用名称
            }

            payload = {
                "model": model,
                "prompt": prompt,
                "n": n,
                "size": size,
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
                import base64
                image_bytes = base64.b64decode(b64_json)
                output_file.write_bytes(image_bytes)
            elif image_url:
                # URL 形式的图像
                image_response = requests.get(image_url, timeout=30)
                if image_response.status_code != 200:
                    return ToolResult(
                        success=False,
                        error=f"下载图像失败: {image_response.status_code}",
                    )
                output_file.write_bytes(image_response.content)
            else:
                return ToolResult(
                    success=False,
                    error="未获取到图像数据或URL",
                )

            return ToolResult(
                success=True,
                data={
                    "image_path": str(output_file),
                    "provider": "openrouter",
                    "model": model,
                    "image_url": image_url,
                },
            )

        except requests.exceptions.Timeout:
            return ToolResult(success=False, error="API 请求超时")
        except Exception as e:
            return ToolResult(success=False, error=f"图像生成失败: {str(e)}")
