"""
日志接口定义
"""

from abc import ABC, abstractmethod
from typing import Dict, Any


class IPluginLogger(ABC):
    """插件日志接口"""

    @abstractmethod
    def debug(self, message: str, **kwargs: Any) -> None:
        pass

    @abstractmethod
    def info(self, message: str, **kwargs: Any) -> None:
        pass

    @abstractmethod
    def warn(self, message: str, **kwargs: Any) -> None:
        pass

    @abstractmethod
    def error(self, message: str, exception: Exception = None, **kwargs: Any) -> None:
        pass

    @abstractmethod
    def with_fields(self, **fields: str) -> 'IPluginLogger':
        """创建带上下文字段的子日志实例"""
        pass


class ILoggerFactory(ABC):
    """统一日志工厂"""

    @abstractmethod
    def for_plugin(self, plugin_id: str) -> IPluginLogger:
        """为指定插件创建日志实例"""
        pass
