"""
消息总线接口定义
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Callable, Optional


class IMessageBus(ABC):
    """发布订阅消息总线"""

    @abstractmethod
    async def publish(self, topic: str, payload: Dict[str, Any], qos: int = 0) -> None:
        """
        发布消息
        qos: 0=最多一次, 1=至少一次, 2=恰好一次
        """
        pass

    @abstractmethod
    async def subscribe(self, topic_pattern: str,
                       callback: Callable[[str, Dict[str, Any]], None]) -> str:
        """
        订阅消息，支持通配符
        返回订阅ID，用于取消订阅
        """
        pass

    @abstractmethod
    async def unsubscribe(self, subscription_id: str) -> None:
        """取消订阅"""
        pass

    @abstractmethod
    async def request(self, service: str, payload: Dict[str, Any],
                     timeout: float = 30.0) -> Dict[str, Any]:
        """
        请求-响应模式：调用其他插件提供的服务"""
        pass

    @abstractmethod
    def register_service(self, service: str, handler: Callable) -> None:
        """注册服务提供者，响应 request 调用"""
        pass
