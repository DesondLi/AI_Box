"""
插件注册表测试用例

测试目标：
1. 插件注册与查询
2. 生命周期状态管理
3. 依赖拓扑排序
4. 循环依赖检测
5. 能力注册与发现
"""
import pytest
from kernel.core.plugin_registry import PluginRegistry, PluginEntry
from kernel.interfaces import IPlugin, PluginLifeCycle


class MockPlugin(IPlugin):
    """Mock 插件用于测试"""
    def __init__(self, plugin_id: str, deps: list = None):
        self._plugin_id = plugin_id
        self._deps = deps or []

    @property
    def plugin_id(self) -> str:
        return self._plugin_id

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def dependencies(self) -> list:
        return self._deps

    async def install(self, context):
        pass

    async def start(self):
        pass

    async def stop(self):
        pass

    async def uninstall(self):
        pass


class TestPluginRegistry:
    """插件注册表测试"""

    def test_register_and_get_plugin(self):
        """测试：注册插件后可以正确获取"""
        registry = PluginRegistry()
        plugin = MockPlugin("test.plugin")

        registry.register(plugin)
        retrieved = registry.get("test.plugin")

        assert retrieved is plugin
        assert registry.get_state("test.plugin") == PluginLifeCycle.CREATED

    def test_register_duplicate_raises_error(self):
        """测试：重复注册同一插件应抛出异常"""
        registry = PluginRegistry()
        plugin = MockPlugin("test.plugin")

        registry.register(plugin)

        with pytest.raises(ValueError, match="already registered"):
            registry.register(plugin)

    def test_get_nonexistent_plugin_returns_none(self):
        """测试：获取不存在的插件返回 None"""
        registry = PluginRegistry()
        assert registry.get("nonexistent") is None

    def test_set_and_get_state(self):
        """测试：状态设置与查询"""
        registry = PluginRegistry()
        plugin = MockPlugin("test.plugin")
        registry.register(plugin)

        registry.set_state("test.plugin", PluginLifeCycle.INSTALLING)
        assert registry.get_state("test.plugin") == PluginLifeCycle.INSTALLING

        registry.set_state("test.plugin", PluginLifeCycle.RUNNING)
        assert registry.get_state("test.plugin") == PluginLifeCycle.RUNNING

    def test_list_all_returns_all_plugin_ids(self):
        """测试：列出所有已注册的插件ID"""
        registry = PluginRegistry()
        registry.register(MockPlugin("plugin.a"))
        registry.register(MockPlugin("plugin.b"))
        registry.register(MockPlugin("plugin.c"))

        result = registry.list_all()
        assert len(result) == 3
        assert set(result) == {"plugin.a", "plugin.b", "plugin.c"}

    def test_capability_registration(self):
        """测试：能力注册与获取"""
        registry = PluginRegistry()

        provider = object()
        registry.register_capability("service.echo", provider)

        assert registry.get_capability("service.echo") is provider

    def test_get_nonexistent_capability_returns_none(self):
        """测试：获取不存在的能力返回 None"""
        registry = PluginRegistry()
        assert registry.get_capability("nonexistent") is None

    def test_resolve_dependencies_simple_chain(self):
        """测试：简单依赖链的拓扑排序"""
        registry = PluginRegistry()
        # A 依赖 B，B 依赖 C → 启动顺序应该是 C → B → A
        registry.register(MockPlugin("plugin.a", ["plugin.b"]))
        registry.register(MockPlugin("plugin.b", ["plugin.c"]))
        registry.register(MockPlugin("plugin.c", []))

        order = registry.resolve_dependencies()

        # 验证顺序正确性：C 在 B 前，B 在 A 前
        assert order.index("plugin.c") < order.index("plugin.b")
        assert order.index("plugin.b") < order.index("plugin.a")

    def test_resolve_dependencies_no_deps(self):
        """测试：无依赖插件的顺序"""
        registry = PluginRegistry()
        registry.register(MockPlugin("plugin.a", []))
        registry.register(MockPlugin("plugin.b", []))

        order = registry.resolve_dependencies()

        # 无依赖时顺序不保证，但两个插件都应在列表中
        assert len(order) == 2
        assert "plugin.a" in order
        assert "plugin.b" in order

    def test_resolve_dependencies_circular_detection(self):
        """测试：循环依赖检测"""
        registry = PluginRegistry()
        # A 依赖 B，B 依赖 A → 循环
        registry.register(MockPlugin("plugin.a", ["plugin.b"]))
        registry.register(MockPlugin("plugin.b", ["plugin.a"]))

        with pytest.raises(ValueError, match="Circular dependency"):
            registry.resolve_dependencies()

    def test_resolve_dependencies_ignores_unregistered_deps(self):
        """测试：未注册的依赖被忽略"""
        registry = PluginRegistry()
        # A 依赖不存在的插件 X → 应该只返回 A
        registry.register(MockPlugin("plugin.a", ["plugin.x"]))

        order = registry.resolve_dependencies()
        assert order == ["plugin.a"]

    def test_get_entry_returns_full_entry(self):
        """测试：获取完整插件条目"""
        registry = PluginRegistry()
        plugin = MockPlugin("test.plugin")
        registry.register(plugin)

        entry = registry.get_entry("test.plugin")

        assert isinstance(entry, PluginEntry)
        assert entry.plugin is plugin
        assert entry.state == PluginLifeCycle.CREATED
        assert entry.context is None
