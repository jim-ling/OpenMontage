"""阿里云 DashScope 提供商适配器（增强版）

支持最新的模型：
- 图像生成：Qwen-Image Pro (首选), HappyHorse 1.1, Wan 2.7 (极致画质)
- 视频生成：可灵 v3 (Kling), 万相 2.7/2.2/2.1
"""

from __future__ import annotations
import time
import requests
from typing import Any, Dict, Optional
from pathlib import Path

from .base_adapter import BaseProviderAdapter, AdapterResult


class DashScopeAdapter(BaseProviderAdapter):
    """阿里云 DashScope 适配器（增强版）"""

    # API 端点配置
    VIDEO_SYNTHESIS_ENDPOINT = "https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis"
    IMAGE2VIDEO_ENDPOINT = "https://dashscope.aliyuncs.com/api/v1/services/aigc/image2video/video-synthesis"

    # 模型分类
    KLING_MODELS = {
        "kling-v3": "kling/kling-v3-video-generation",
        "kling-v3-omni": "kling/kling-v3-omni-video-generation",
    }

    WAN_MODELS = {
        "wan2.7-t2v": "wan2.7-t2v-2026-06-12",
        "wan2.7-i2v": "wan2.7-i2v-2026-04-25",
        "wan2.7-r2v": "wan2.7-r2v-2026-06-12",
        "wan2.2-animate": "wan2.2-animate-move",
    }

    # 图像生成模型（按推荐优先级）
    IMAGE_MODELS = {
        "qwen-image-pro": "qwen/qwen-image-pro",  # 首选：效果最好
        "qwen-image": "qwen/qwen-image",
        "happyhorse": "happyhorse/happyhorse-1.1",  # 综合表现突出
        "wan2.7": "wan2.7-image",  # 极致画质和光影
        "wanx-v1": "wanx-v1",  # 传统万相
    }

    def __init__(self, api_key: str, workspace_id: str = None, **kwargs):
        super().__init__(api_key, **kwargs)
        self.workspace_id = workspace_id

        # 延迟导入，避免没安装 SDK 时报错
        try:
            import dashscope
            dashscope.api_key = api_key
            self.dashscope = dashscope
            self._sdk_available = True
        except ImportError:
            self._sdk_available = False
            self.dashscope = None

    @property
    def provider_name(self) -> str:
        return "dashscope"

    def is_available(self) -> bool:
        return super().is_available() and self._sdk_available

    def generate_image(
        self,
        prompt: str,
        size: str = "1024x1024",
        n: int = 1,
        output_path: str = None,
        **kwargs
    ) -> AdapterResult:
        """使用 DashScope SDK 生成图像

        推荐模型优先级：
        1. qwen-image-pro - 效果最好（首选）
        2. happyhorse-1.1 - 综合表现突出
        3. wan2.7 - 极致画质和光影
        """

        if not self.is_available():
            return AdapterResult(
                success=False,
                error="DashScope SDK 未安装或 API key 未配置",
                provider=self.provider_name
            )

        try:
            from dashscope import ImageSynthesis

            # 默认使用 Qwen-Image Pro（效果最好）
            model = kwargs.get('model', 'qwen-image-pro')

            # 转换尺寸格式: "1024x1024" -> "1024*1024"
            dashscope_size = size.replace("x", "*")

            # 调用图像生成
            response = ImageSynthesis.call(
                model=model,
                prompt=prompt,
                n=n,
                size=dashscope_size,
                style=kwargs.get('style'),
                negative_prompt=kwargs.get('negative_prompt')
            )

            # 检查响应
            if response.status_code != 200:
                return AdapterResult(
                    success=False,
                    error=f"DashScope API 失败: {response.code} - {response.message}",
                    provider=self.provider_name
                )

            # 获取图像 URL
            results = response.output.get('results', [])
            if not results:
                return AdapterResult(
                    success=False,
                    error="未获取到图像结果",
                    provider=self.provider_name
                )

            image_url = results[0].get('url')

            # 如果提供了 output_path，下载图像
            if output_path and image_url:
                downloaded_path = self._download_image(image_url, output_path)
                if not downloaded_path:
                    return AdapterResult(
                        success=False,
                        error="图像下载失败",
                        provider=self.provider_name
                    )
            else:
                downloaded_path = None

            # 计算成本（阿里云百炼图像成本约 ¥0.08/张）
            cost = self._calculate_cost('image', n)

            return AdapterResult(
                success=True,
                data={
                    'image_url': image_url,
                    'image_path': downloaded_path,
                    'model': model,
                    'size': size,
                },
                provider=self.provider_name,
                cost=cost,
                metadata={
                    'task_id': response.output.get('task_id'),
                    'request_id': response.request_id
                }
            )

        except Exception as e:
            return AdapterResult(
                success=False,
                error=f"DashScope 图像生成异常: {str(e)}",
                provider=self.provider_name
            )

    def generate_video(
        self,
        prompt: str,
        duration: int = 5,
        aspect_ratio: str = "16:9",
        output_path: str = None,
        **kwargs
    ) -> AdapterResult:
        """使用新版 REST API 生成视频（支持可灵和万相最新模型）"""

        if not self.api_key:
            return AdapterResult(
                success=False,
                error="API key 未配置",
                provider=self.provider_name
            )

        # 确定使用的模型
        model = kwargs.pop('model', 'wan2.7-t2v-2026-06-12')

        # 根据模型选择端点和参数
        if model.startswith('kling/') or model in self.KLING_MODELS.values():
            return self._generate_video_kling(prompt, duration, aspect_ratio, output_path, model, **kwargs)
        elif model.startswith('wan2.2-animate'):
            return self._generate_video_animate_move(output_path, model, **kwargs)
        else:
            return self._generate_video_wan(prompt, duration, aspect_ratio, output_path, model, **kwargs)

    def _generate_video_wan(
        self,
        prompt: str,
        duration: int,
        aspect_ratio: str,
        output_path: str,
        model: str,
        **kwargs
    ) -> AdapterResult:
        """万相系列视频生成（wan2.7, wan2.1）"""

        # 构建请求体
        payload = {
            "model": model,
            "input": {
                "prompt": prompt,
            },
            "parameters": {
                "resolution": kwargs.get('resolution', '720P'),
                "ratio": aspect_ratio,
                "duration": duration,
                "prompt_extend": kwargs.get('prompt_extend', True),
                "watermark": kwargs.get('watermark', False),
            }
        }

        # 添加参考图片（用于 i2v, r2v）
        if kwargs.get('media'):
            payload["input"]["media"] = kwargs['media']
        elif kwargs.get('image_url'):
            payload["input"]["media"] = [{
                "type": "first_frame",
                "url": kwargs['image_url']
            }]

        # 确定端点（工作空间模型需要特殊端点）
        if model.startswith('wan2.7') and self.workspace_id:
            endpoint = f"https://{self.workspace_id}.cn-beijing.maas.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis"
        else:
            endpoint = self.VIDEO_SYNTHESIS_ENDPOINT

        return self._async_video_request(endpoint, payload, output_path, model)

    def _generate_video_kling(
        self,
        prompt: str,
        duration: int,
        aspect_ratio: str,
        output_path: str,
        model: str,
        **kwargs
    ) -> AdapterResult:
        """可灵系列视频生成"""

        payload = {
            "model": model,
            "input": {
                "prompt": prompt,
            },
            "parameters": {
                "mode": kwargs.get('mode', 'std'),  # std 或 pro
                "aspect_ratio": aspect_ratio,
                "duration": duration,
                "audio": kwargs.get('audio', False),
                "watermark": kwargs.get('watermark', False),
            }
        }

        # 多镜头支持
        if kwargs.get('multi_prompt'):
            payload["input"]["multi_shot"] = True
            payload["input"]["shot_type"] = kwargs.get('shot_type', 'customize')
            payload["input"]["multi_prompt"] = kwargs['multi_prompt']

        # 媒体输入（图转视频等）
        if kwargs.get('media'):
            payload["input"]["media"] = kwargs['media']

        return self._async_video_request(self.VIDEO_SYNTHESIS_ENDPOINT, payload, output_path, model)

    def _generate_video_animate_move(
        self,
        output_path: str,
        model: str,
        **kwargs
    ) -> AdapterResult:
        """动作迁移（wan2.2-animate-move）"""

        if not kwargs.get('image_url') or not kwargs.get('video_url'):
            return AdapterResult(
                success=False,
                error="animate-move 需要 image_url 和 video_url 参数",
                provider=self.provider_name
            )

        payload = {
            "model": model,
            "input": {
                "image_url": kwargs['image_url'],
                "video_url": kwargs['video_url'],
                "watermark": kwargs.get('watermark', True),
            },
            "parameters": {
                "mode": kwargs.get('mode', 'wan-std')
            }
        }

        return self._async_video_request(self.IMAGE2VIDEO_ENDPOINT, payload, output_path, model)

    def _async_video_request(
        self,
        endpoint: str,
        payload: dict,
        output_path: str,
        model: str
    ) -> AdapterResult:
        """异步视频生成请求通用处理"""

        headers = {
            'X-DashScope-Async': 'enable',
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }

        try:
            # 提交任务
            response = requests.post(endpoint, headers=headers, json=payload, timeout=30)
            result = response.json()

            if response.status_code != 200 or result.get('code'):
                return AdapterResult(
                    success=False,
                    error=f"任务提交失败: {result.get('code')} - {result.get('message')}",
                    provider=self.provider_name
                )

            task_id = result['output']['task_id']

            # 轮询任务状态
            return self._poll_video_task_rest(task_id, output_path, model, max_wait=900)

        except Exception as e:
            return AdapterResult(
                success=False,
                error=f"视频生成异常: {str(e)}",
                provider=self.provider_name
            )

    def _poll_video_task_rest(
        self,
        task_id: str,
        output_path: str,
        model: str,
        max_wait: int = 300
    ) -> AdapterResult:
        """轮询 REST API 任务状态"""

        headers = {
            'Authorization': f'Bearer {self.api_key}',
        }

        query_url = f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"

        elapsed = 0
        poll_interval = 5

        while elapsed < max_wait:
            time.sleep(poll_interval)
            elapsed += poll_interval

            try:
                response = requests.get(query_url, headers=headers, timeout=10)
                result = response.json()

                if response.status_code != 200:
                    continue

                status = result['output']['task_status']

                if status == 'SUCCEEDED':
                    video_url = result['output'].get('video_url')

                    if not video_url:
                        return AdapterResult(
                            success=False,
                            error="任务完成但未获取到视频 URL",
                            provider=self.provider_name
                        )

                    # 下载视频
                    if output_path:
                        downloaded_path = self._download_video(video_url, output_path)
                        if not downloaded_path:
                            return AdapterResult(
                                success=False,
                                error="视频下载失败",
                                provider=self.provider_name
                            )
                    else:
                        downloaded_path = None

                    # 计算成本
                    cost = self._calculate_cost_by_model(model)

                    return AdapterResult(
                        success=True,
                        data={
                            'video_url': video_url,
                            'video_path': downloaded_path,
                            'duration': result['output'].get('duration'),
                        },
                        provider=self.provider_name,
                        cost=cost,
                        metadata={
                            'task_id': task_id,
                            'model': model,
                        }
                    )

                elif status == 'FAILED':
                    error_msg = result['output'].get('message', '未知错误')
                    return AdapterResult(
                        success=False,
                        error=f"视频生成失败: {error_msg}",
                        provider=self.provider_name
                    )

            except Exception as e:
                continue

        return AdapterResult(
            success=False,
            error=f"视频生成超时（等待了 {elapsed} 秒）",
            provider=self.provider_name
        )

    def _download_image(self, url: str, output_path: str) -> str:
        """下载图像到本地"""
        try:
            response = requests.get(url, timeout=30)
            if response.status_code != 200:
                return None

            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            output_file.write_bytes(response.content)

            return str(output_file)
        except Exception:
            return None

    def _download_video(self, url: str, output_path: str) -> str:
        """下载视频到本地"""
        return self._download_image(url, output_path)

    def _calculate_cost(self, resource_type: str, quantity: int) -> float:
        """计算成本（转换为美元）"""
        # 阿里云百炼成本（人民币）
        cost_table = {
            'image': 0.08,  # ¥0.08/张
            'video': 1.50,  # ¥1.50/5秒片段
        }

        rmb_cost = cost_table.get(resource_type, 0) * quantity

        # 转换为美元（汇率约 7.2）
        usd_cost = rmb_cost / 7.2

        return round(usd_cost, 4)

    def _calculate_cost_by_model(self, model: str) -> float:
        """根据模型计算成本"""
        # 不同模型的定价（人民币/5秒）
        model_pricing = {
            'wan2.7': 1.50,
            'wan2.2': 1.50,
            'wanx2.1': 1.50,
            'kling-v3': 2.00,  # 可灵价格较高
        }

        # 匹配模型前缀
        for prefix, price in model_pricing.items():
            if model.startswith(prefix) or prefix in model:
                return round(price / 7.2, 4)  # 转美元

        # 默认价格
        return round(1.50 / 7.2, 4)
