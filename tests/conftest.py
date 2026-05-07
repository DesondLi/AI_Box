"""
测试共享 fixtures

提供：
- 事件循环优化
- 内核上下文
- 配置注册表
- 消息总线
- Mock 插件工厂
"""
import pytest
import asyncio
from typing import Callable, Any


@pytest.fixture(scope="session")
def event_loop():
    """全局事件循环，加速异步测试"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def empty_kernel():
    """干净的微内核实例，无插件注册"""
    from kernel.core.kernel import MicroKernel
    return MicroKernel()


@pytest.fixture
def temp_config():
    """临时配置注册表，测试后自动清理监听器"""
    from kernel.core.memory_config import MemoryConfigRegistry
    config = MemoryConfigRegistry()
    yield config
    # 测试后清理所有 watchers
    config._watchers.clear()


@pytest.fixture
def empty_message_bus():
    """干净的消息总线实例"""
    from kernel.core.memory_message_bus import MemoryMessageBus
    return MemoryMessageBus()


@pytest.fixture
def tracker_logger():
    """可捕获日志内容的 logger 实例"""
    from kernel.core.console_logger import ConsoleLogger

    class TrackerLogger(ConsoleLogger):
        def __init__(self):
            super().__init__()
            self.logs = []

        def _log(self, level: str, message: str, **kwargs):
            self.logs.append((level, message))
            # 不调用父类避免控制台输出

    return TrackerLogger()


@pytest.fixture
def mock_plugin_factory():
    """Mock 插件工厂，支持依赖注入和失败模拟

    用法:
        plugin = mock_plugin_factory("test.id", deps=["other"], fail_at="install")
    """
    from tests.unit.test_helpers import MockPlugin

    def factory(plugin_id, deps=None, fail_at=None):
        return MockPlugin(plugin_id, deps or [], fail_at)

    return factory
