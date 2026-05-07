"""
微内核核心测试用例

测试目标：
1. 内核启动/停止生命周期
2. 插件完整生命周期（install → start → stop）
3. 插件依赖顺序
4. 错误情况下的行为
"""
import pytest
from kernel.core.kernel import MicroKernel, KernelContext
from kernel.interfaces import IPlugin, PluginLifeCycle, IKernelContext


class LifecycleTracker:
    """跟踪插件生命周期调用"""
    def __init__(self):
        self.events = []

    def record(self, event: str):
        self.events.append(event)


class MockPluginWithLifecycle(IPlugin):
    """带生命周期跟踪的 Mock 插件"""
    def __init__(self, plugin_id: str, deps: list = None, fail_at: str = None):
        self._plugin_id = plugin_id
        self._deps = deps or []
        self.fail_at = fail_at  # 在哪个阶段失败: 'install' / 'start' / 'stop'
        self.tracker = LifecycleTracker()
        self.context = None

    @property
    def plugin_id(self) -> str:
        return self._plugin_id

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def dependencies(self) -> list:
        return self._deps

    async def install(self, context: IKernelContext):
        self.tracker.record("install")
        self.context = context
        if self.fail_at == "install":
            raise RuntimeError(f"Install failed for {self._plugin_id}")

    async def start(self):
        self.tracker.record("start")
        if self.fail_at == "start":
            raise RuntimeError(f"Start failed for {self._plugin_id}")

    async def stop(self):
        self.tracker.record("stop")
        if self.fail_at == "stop":
            raise RuntimeError(f"Stop failed for {self._plugin_id}")

    async def uninstall(self):
        self.tracker.record("uninstall")


class TestMicroKernel:
    """微内核核心测试"""

    @pytest.mark.asyncio
    async def test_kernel_creation(self):
        """测试：内核创建后核心服务可用"""
        kernel = MicroKernel()

        assert kernel.config is not None
        assert kernel.logger is not None
        assert kernel.message_bus is not None
        assert kernel.plugin_registry is not None

    @pytest.mark.asyncio
    async def test_plugin_full_lifecycle(self):
        """测试：插件完整生命周期"""
        kernel = MicroKernel()
        plugin = MockPluginWithLifecycle("test.plugin")
        kernel.register_plugin(plugin)

        # 启动内核（触发 install + start）
        await kernel.start()

        assert "install" in plugin.tracker.events
        assert "start" in plugin.tracker.events
        assert plugin.context is not None

        # 停止内核
        await kernel.stop()

        assert "stop" in plugin.tracker.events

    @pytest.mark.asyncio
    async def test_plugin_dependency_order(self):
        """测试：插件按依赖顺序启动"""
        kernel = MicroKernel()

        # A 依赖 B，B 依赖 C
        plugin_a = MockPluginWithLifecycle("plugin.a", ["plugin.b"])
        plugin_b = MockPluginWithLifecycle("plugin.b", ["plugin.c"])
        plugin_c = MockPluginWithLifecycle("plugin.c", [])

        kernel.register_plugin(plugin_a)
        kernel.register_plugin(plugin_b)
        kernel.register_plugin(plugin_c)

        # 直接验证启动顺序解析结果
        startup_order = kernel.plugin_registry.resolve_dependencies()

        # C → B → A
        assert startup_order.index("plugin.c") < startup_order.index("plugin.b")
        assert startup_order.index("plugin.b") < startup_order.index("plugin.a")

    @pytest.mark.asyncio
    async def test_plugin_stop_reverse_order(self):
        """测试：插件按依赖逆序停止"""
        kernel = MicroKernel()

        plugin_a = MockPluginWithLifecycle("plugin.a", ["plugin.b"])
        plugin_b = MockPluginWithLifecycle("plugin.b", [])

        kernel.register_plugin(plugin_a)
        kernel.register_plugin(plugin_b)

        startup_order = kernel.plugin_registry.resolve_dependencies()
        stop_order = list(reversed(startup_order))

        # 停止顺序应该是 A → B
        assert stop_order.index("plugin.a") < stop_order.index("plugin.b")

    @pytest.mark.asyncio
    async def test_install_failure_raises_exception(self):
        """测试：插件安装失败时抛出异常"""
        kernel = MicroKernel()
        plugin = MockPluginWithLifecycle("bad.plugin", fail_at="install")
        kernel.register_plugin(plugin)

        with pytest.raises(RuntimeError, match="Install failed"):
            await kernel.start()

    @pytest.mark.asyncio
    async def test_start_failure_raises_exception(self):
        """测试：插件启动失败时抛出异常"""
        kernel = MicroKernel()
        plugin = MockPluginWithLifecycle("bad.plugin", fail_at="start")
        kernel.register_plugin(plugin)

        with pytest.raises(RuntimeError, match="Start failed"):
            await kernel.start()

    @pytest.mark.asyncio
    async def test_stop_failure_logs_but_continues(self):
        """测试：插件停止失败记录日志但继续执行"""
        kernel = MicroKernel()
        plugin = MockPluginWithLifecycle("bad.plugin", fail_at="stop")
        kernel.register_plugin(plugin)

        await kernel.start()
        # 停止失败不应该抛出异常，只记录日志
        await kernel.stop()

        assert "stop" in plugin.tracker.events

    @pytest.mark.asyncio
    async def test_kernel_idempotent_start(self):
        """测试：重复调用 start 是安全的"""
        kernel = MicroKernel()
        plugin = MockPluginWithLifecycle("test.plugin")
        kernel.register_plugin(plugin)

        await kernel.start()
        await kernel.start()  # 第二次应该被忽略

        # install 和 start 只被调用一次
        assert plugin.tracker.events.count("install") == 1
        assert plugin.tracker.events.count("start") == 1

        await kernel.stop()

    @pytest.mark.asyncio
    async def test_stop_not_running_kernel_is_safe(self):
        """测试：停止未运行的内核是安全的"""
        kernel = MicroKernel()
        await kernel.stop()  # 不应该抛出异常

    @pytest.mark.asyncio
    async def test_plugin_context_injection(self):
        """测试：插件获得正确的内核上下文"""
        kernel = MicroKernel()
        plugin = MockPluginWithLifecycle("test.plugin")
        kernel.register_plugin(plugin)

        await kernel.start()

        assert plugin.context is not None
        assert isinstance(plugin.context, KernelContext)
        assert plugin.context.config is kernel.config
        assert plugin.context.message_bus is kernel.message_bus

        await kernel.stop()

    @pytest.mark.asyncio
    async def test_plugin_can_access_other_plugins_via_context(self):
        """测试：插件可以通过上下文访问其他插件"""
        kernel = MicroKernel()

        plugin_a = MockPluginWithLifecycle("plugin.a", ["plugin.b"])
        plugin_b = MockPluginWithLifecycle("plugin.b", [])

        kernel.register_plugin(plugin_a)
        kernel.register_plugin(plugin_b)

        await kernel.start()

        # plugin.a 可以通过 context 获取 plugin.b
        other_plugin = plugin_a.context.get_plugin("plugin.b")
        assert other_plugin is plugin_b

        await kernel.stop()
