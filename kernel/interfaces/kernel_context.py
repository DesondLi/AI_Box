"""
内核上下文接口定义
"""

from abc import ABC, abstractmethod
from typing import Optional, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .plugin import IPlugin
    from .config import IConfigRegistry
    from .logger import ILoggerFactory
    from .message_bus import IMessageBus


class IKernelContext(ABC):
    """插件与内核交互的唯一入口"""

    @property
    @abstractmethod
    def config(self) -> 'IConfigRegistry':
        """配置注册表"""
        pass

    @property
    @abstractmethod
    def logger(self) -> 'ILoggerFactory':
        """日志工厂"""
        pass

    @property
    @abstractmethod
    def message_bus(self) -> 'IMessageBus':
        """消息总线"""
        pass

    @abstractmethod
    def get_plugin(self, plugin_id: str) -> Optional['IPlugin']:
        """获取其他插件实例（用于能力调用）"""
        pass

    @abstractmethod
    def register_capability(self, capability: str, provider: Any) -> None:
        """注册能力，供其他插件发现和调用"""
        pass

    @abstractmethod
    def get_capability(self, capability: str) -> Optional[Any]:
        """获取能力提供者"""
        pass
