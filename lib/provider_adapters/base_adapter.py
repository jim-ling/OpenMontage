"""提供商适配器基类

定义所有提供商适配器的统一接口
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from dataclasses import dataclass


@dataclass
class AdapterResult:
    """适配器返回结果"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    provider: Optional[str] = None
    cost: float = 0.0
    metadata: Optional[Dict[str, Any]] = None


class BaseProviderAdapter(ABC):
    """提供商适配器基类"""

    def __init__(self, api_key: str, **kwargs):
        self.api_key = api_key
        self.config = kwargs

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """提供商名称"""
        pass

    @abstractmethod
    def generate_image(
        self,
        prompt: str,
        size: str = "1024x1024",
        n: int = 1,
        **kwargs
    ) -> AdapterResult:
        """生成图像

        Args:
            prompt: 图像描述
            size: 图像尺寸
            n: 生成数量
            **kwargs: 其他参数

        Returns:
            AdapterResult: 统一的结果对象
        """
        pass

    @abstractmethod
    def generate_video(
        self,
        prompt: str,
        duration: int = 5,
        aspect_ratio: str = "16:9",
        **kwargs
    ) -> AdapterResult:
        """生成视频

        Args:
            prompt: 视频描述
            duration: 时长（秒）
            aspect_ratio: 宽高比
            **kwargs: 其他参数

        Returns:
            AdapterResult: 统一的结果对象
        """
        pass

    def is_available(self) -> bool:
        """检查提供商是否可用"""
        return bool(self.api_key)

    def _normalize_size(self, size: str) -> str:
        """标准化尺寸格式

        将不同格式转换为提供商需要的格式
        例如: "1024x1024" -> "1024*1024" (DashScope)
        """
        return size

    def _calculate_cost(self, resource_type: str, quantity: int) -> float:
        """计算成本

        Args:
            resource_type: 资源类型 (image, video)
            quantity: 数量

        Returns:
            float: 成本（美元）
        """
        return 0.0
