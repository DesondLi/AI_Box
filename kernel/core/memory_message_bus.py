"""
内存消息总线实现

支持：
- publish/subscribe
- MQTT 3.1.1 风格通配符 (+ 单层, # 多层)
- request/response 模式
"""

import asyncio
import uuid
from typing import Dict, Any, Callable, List, Tuple

from kernel.interfaces import IMessageBus


class MemoryMessageBus(IMessageBus):
    """基于内存的消息总线实现"""

    def __init__(self):
        self._subscriptions: Dict[str, Tuple[str, Callable]] = {}  # sub_id -> (pattern, callback)
        self._services: Dict[str, Callable] = {}
        self._response_futures: Dict[str, asyncio.Future] = {}

    def _match_topic(self, pattern: str, topic: str) -> bool:
        """
        MQTT 3.1.1 风格主题匹配

        规则：
        - `+` 单层通配符：精确匹配一个层级
        - `#` 多层通配符：匹配零个或多个层级（必须在结尾）
        - 层级分隔符：`/`

        示例：
        - sensor/+ → sensor/temp ✓, sensor/hum ✓, sensor ✗, sensor/a/b ✗
        - sensor/# → sensor ✓, sensor/temp ✓, sensor/a/b ✓
        - + → temp ✓, "" ✗ (空主题是零层级)
        - # → temp ✓, sensor/temp ✓, "" ✓
        """
        # 快速路径：精确匹配
        if pattern == topic:
            return True

        # 空主题特殊处理：只有 # 匹配空（零层级）
        if topic == "":
            return pattern == "#"

        # 按层级分割
        pattern_parts = pattern.split('/')
        topic_parts = topic.split('/')

        # 处理 # 通配符（只能在最后）
        has_hash = False
        if pattern_parts and pattern_parts[-1] == '#':
            has_hash = True
            pattern_parts = pattern_parts[:-1]  # 移除 #，只匹配前缀

        # 没有 # 时，层级数量必须相等
        if not has_hash and len(pattern_parts) != len(topic_parts):
            return False

        # 有 # 时，主题层级不能比模式少（# 前的部分）
        if has_hash and len(topic_parts) < len(pattern_parts):
            return False

        # 逐个层级匹配
        for p_part, t_part in zip(pattern_parts, topic_parts):
            if p_part == '+':
                # + 匹配任意单个层级（包括空字符串，如 // 表示的空层级）
                continue
            elif p_part != t_part:
                return False

        return True

    async def publish(self, topic: str, payload: Dict[str, Any], qos: int = 0) -> None:
        """发布消息"""
        # 找到所有匹配的订阅
        callbacks: List[Callable] = []
        for sub_id, (pattern, callback) in self._subscriptions.items():
            if self._match_topic(pattern, topic):
                callbacks.append(callback)

        # 并行调用所有回调
        if callbacks:
            await asyncio.gather(*[
                callback(topic, dict(payload))  # 复制 payload 防止副作用
                for callback in callbacks
            ], return_exceptions=True)

    async def subscribe(self, topic_pattern: str,
                       callback: Callable[[str, Dict[str, Any]], None]) -> str:
        """订阅消息"""
        sub_id = f"sub-{uuid.uuid4().hex[:8]}"
        self._subscriptions[sub_id] = (topic_pattern, callback)
        return sub_id

    async def unsubscribe(self, subscription_id: str) -> None:
        """取消订阅"""
        self._subscriptions.pop(subscription_id, None)

    async def request(self, service: str, payload: Dict[str, Any],
                     timeout: float = 30.0) -> Dict[str, Any]:
        """请求-响应模式"""
        handler = self._services.get(service)
        if not handler:
            raise ValueError(f"Service {service} not found")

        # 直接调用（内存中不需要网络传输）
        result = await handler(payload)
        return result if isinstance(result, dict) else {"result": result}

    def register_service(self, service: str, handler: Callable) -> None:
        """注册服务提供者"""
        self._services[service] = handler
