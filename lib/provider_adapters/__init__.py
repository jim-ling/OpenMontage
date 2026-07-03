"""提供商适配器模块

统一的多提供商接口
"""

from .base_adapter import BaseProviderAdapter, AdapterResult
from .dashscope_adapter import DashScopeAdapter

__all__ = [
    'BaseProviderAdapter',
    'AdapterResult',
    'DashScopeAdapter',
]
