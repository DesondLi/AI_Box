"""
配置注册表接口定义
"""

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Optional


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

    # --- 持久化接口 ---

    @abstractmethod
    def save(self, path: Optional[str] = None) -> None:
        """
        保存配置到文件

        Args:
            path: 文件路径，None 表示使用默认路径
        """
        pass

    @abstractmethod
    def load(self, path: Optional[str] = None) -> None:
        """
        从文件加载配置

        Args:
            path: 文件路径，None 表示使用默认路径
        """
        pass

    @abstractmethod
    def enable_hotreload(self, path: Optional[str] = None, interval: float = 1.0) -> None:
        """
        启用热重载，自动监听文件变更

        Args:
            path: 监听的文件路径，None 表示使用默认路径
            interval: 轮询间隔（秒）
        """
        pass

    @abstractmethod
    def disable_hotreload(self) -> None:
        """禁用热重载"""
        pass

    @property
    @abstractmethod
    def has_hotreload(self) -> bool:
        """是否启用了热重载"""
        pass
