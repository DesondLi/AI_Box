"""
消息总线测试用例

测试目标：
1. publish/subscribe 模式
2. request/response 模式（服务调用）
3. 主题匹配规则
4. 异步消息传递
"""
import pytest
import asyncio
from kernel.core.memory_message_bus import MemoryMessageBus


class TestMemoryMessageBus:
    """内存消息总线测试"""

    @pytest.mark.asyncio
    async def test_publish_subscribe_basic(self):
        """测试：基础发布订阅模式"""
        bus = MemoryMessageBus()
        received = []

        async def handler(topic: str, payload: dict):
            received.append((topic, payload))

        await bus.subscribe("test/topic", handler)
        await bus.publish("test/topic", {"key": "value"})

        # 给一点时间让消息传递
        await asyncio.sleep(0.01)

        assert len(received) == 1
        assert received[0] == ("test/topic", {"key": "value"})

    @pytest.mark.asyncio
    async def test_subscribe_prefix_matching(self):
        """测试：主题前缀匹配"""
        bus = MemoryMessageBus()
        received = []

        async def handler(topic: str, payload: dict):
            received.append((topic, payload))

        await bus.subscribe("data/#", handler)

        await bus.publish("data/input", {"data": 1})
        await bus.publish("data/output", {"data": 2})

        await asyncio.sleep(0.01)

        assert len(received) == 2

    @pytest.mark.asyncio
    async def test_no_match_no_delivery(self):
        """测试：不匹配的主题不投递"""
        bus = MemoryMessageBus()
        received = []

        async def handler(topic: str, payload: dict):
            received.append((topic, payload))

        await bus.subscribe("only/this", handler)
        await bus.publish("other/topic", {"key": "value"})

        await asyncio.sleep(0.01)

        assert len(received) == 0

    @pytest.mark.asyncio
    async def test_multiple_subscribers_same_topic(self):
        """测试：同一主题多个订阅者"""
        bus = MemoryMessageBus()
        received1 = []
        received2 = []

        async def handler1(topic: str, payload: dict):
            received1.append(payload)

        async def handler2(topic: str, payload: dict):
            received2.append(payload)

        await bus.subscribe("test/topic", handler1)
        await bus.subscribe("test/topic", handler2)

        await bus.publish("test/topic", {"msg": "hello"})
        await asyncio.sleep(0.01)

        assert len(received1) == 1
        assert len(received2) == 1

    @pytest.mark.asyncio
    async def test_request_response_basic(self):
        """测试：基础请求响应模式"""
        bus = MemoryMessageBus()

        async def echo_handler(request: dict):
            return {"echo": request, "status": "ok"}

        bus.register_service("echo", echo_handler)

        result = await bus.request("echo", {"hello": "world"})

        assert result["echo"] == {"hello": "world"}
        assert result["status"] == "ok"

    @pytest.mark.asyncio
    async def test_request_nonexistent_service_raises(self):
        """测试：调用不存在的服务抛出异常"""
        bus = MemoryMessageBus()

        with pytest.raises(ValueError, match="Service .* not found"):
            await bus.request("nonexistent", {})

    @pytest.mark.asyncio
    async def test_service_handler_exception_propagates(self):
        """测试：服务处理器异常会传播"""
        bus = MemoryMessageBus()

        async def bad_handler(request: dict):
            raise RuntimeError("Something went wrong")

        bus.register_service("bad", bad_handler)

        with pytest.raises(RuntimeError, match="Something went wrong"):
            await bus.request("bad", {})

    @pytest.mark.asyncio
    async def test_unsubscribe_removes_handler(self):
        """测试：取消订阅后不再接收消息"""
        bus = MemoryMessageBus()
        received = []

        async def handler(topic: str, payload: dict):
            received.append((topic, payload))

        sub_id = await bus.subscribe("test/topic", handler)
        await bus.unsubscribe(sub_id)

        await bus.publish("test/topic", {"key": "value"})
        await asyncio.sleep(0.01)

        assert len(received) == 0

    @pytest.mark.asyncio
    async def test_concurrent_message_delivery(self):
        """测试：并发消息投递"""
        bus = MemoryMessageBus()
        received = []

        async def handler(topic: str, payload: dict):
            received.append(payload["id"])

        await bus.subscribe("data/#", handler)

        # 并发发布多条消息
        async def publish_many():
            for i in range(10):
                await bus.publish(f"data/{i}", {"id": i})

        await publish_many()
        await asyncio.sleep(0.05)

        assert len(received) == 10
        assert set(received) == set(range(10))

    @pytest.mark.asyncio
    async def test_service_overwrite(self):
        """测试：注册同名服务会覆盖旧服务"""
        bus = MemoryMessageBus()

        async def handler_v1(request: dict):
            return {"version": 1}

        async def handler_v2(request: dict):
            return {"version": 2}

        bus.register_service("service", handler_v1)
        result1 = await bus.request("service", {})

        bus.register_service("service", handler_v2)
        result2 = await bus.request("service", {})

        assert result1["version"] == 1
        assert result2["version"] == 2


class TestMemoryMessageBusInternals:
    """消息总线内部方法测试"""

    def test_match_topic_exact_match(self):
        """主题精确匹配"""
        bus = MemoryMessageBus()
        assert bus._match_topic("sensor/temp", "sensor/temp")
        assert not bus._match_topic("sensor/temp", "sensor/humidity")

    def test_match_topic_hash_wildcard(self):
        """# 通配符匹配零个或多个层级"""
        bus = MemoryMessageBus()
        # # 单独使用匹配所有
        assert bus._match_topic("#", "any/topic")
        assert bus._match_topic("#", "single")
        assert bus._match_topic("#", "")
        # 前缀/# 匹配前缀开头的
        assert bus._match_topic("sensor/#", "sensor")
        assert bus._match_topic("sensor/#", "sensor/temp")
        assert bus._match_topic("sensor/#", "sensor/temp/room1")
        # 不匹配其他前缀
        assert not bus._match_topic("sensor/#", "actuator/light")

    def test_match_topic_plus_wildcard(self):
        """+ 通配符精确匹配单个层级"""
        bus = MemoryMessageBus()
        # 单层
        assert bus._match_topic("sensor/+", "sensor/temp")
        assert not bus._match_topic("sensor/+", "sensor")  # 必须有一个层级
        assert not bus._match_topic("sensor/+", "sensor/temp/value")  # 不能跨层级
        # 多个 +
        assert bus._match_topic("+/+/temp", "a/b/temp")
        assert bus._match_topic("+/+", "a/b")
        assert not bus._match_topic("+/+", "a/b/c")
        assert not bus._match_topic("+/+", "a")

    def test_match_topic_edge_cases(self):
        """主题匹配边缘情况"""
        bus = MemoryMessageBus()
        # 空主题
        assert bus._match_topic("", "")
        assert not bus._match_topic("", "a")
        # 前导斜杠创建空层级
        assert bus._match_topic("/sensor", "/sensor")
        assert not bus._match_topic("/sensor", "sensor")

    def test_subscription_management_state(self, empty_message_bus):
        """订阅管理内部状态"""
        bus = empty_message_bus
        # 初始状态应该有 _subscriptions
        assert hasattr(bus, "_subscriptions")

    def test_service_registry_state(self, empty_message_bus):
        """服务注册状态管理"""
        bus = empty_message_bus
        assert hasattr(bus, "_services")

        import asyncio

        async def handler(req):
            return {}

        bus.register_service("test", handler)
        assert "test" in bus._services
        assert bus._services["test"] == handler

    def test_service_overwrite_updates_state(self, empty_message_bus):
        """服务覆盖正确更新状态"""
        bus = empty_message_bus

        async def h1(req):
            return {"v": 1}

        async def h2(req):
            return {"v": 2}

        bus.register_service("s", h1)
        bus.register_service("s", h2)

        assert bus._services["s"] == h2
