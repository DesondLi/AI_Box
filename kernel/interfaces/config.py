"""
配置注册表接口定义
"""

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict


class IConfigRegistry(ABC):
    """热重载配置注册表"""

    @abstractmethod
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        pass

    @abstractmethod
    def set(self, key: str, value: Any) -> None:
        """设置配置值（触发变更通知）"""
        pass

    @abstractmethod
    def watch(self, key_pattern: str, callback: Callable[[str, Any], None]) -> str:
        """
        监听配置变更
        key_pattern: 支持通配符 *
        返回: 订阅ID，用于取消监听
        """
        pass

    @abstractmethod
    def unwatch(self, watch_id: str) -> None:
        """取消配置监听"""
        pass

    @abstractmethod
    def get_namespace(self, namespace: str) -> 'IConfigRegistry':
        """获取命名空间下的子配置"""
        pass
