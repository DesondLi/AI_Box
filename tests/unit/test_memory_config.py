"""
MemoryConfig 配置注册表完整测试

测试目标：
1. KV 读写操作
2. watch 监听机制
3. 命名空间隔离
4. bulk_load 批量加载
5. 边界情况和错误处理
"""
import pytest
from tests.unit.test_helpers import CallbackTracker


class TestMemoryConfigBasic:
    """基础 KV 操作测试"""

    def test_get_nonexistent_key_returns_default(self, temp_config):
        """不存在的 key 返回默认值"""
        assert temp_config.get("nonexistent") is None
        assert temp_config.get("nonexistent", "fallback") == "fallback"

    def test_set_and_get_value(self, temp_config):
        """设置值后可以正确读取"""
        temp_config.set("key", "value")
        assert temp_config.get("key") == "value"

    def test_set_overwrites_old_value(self, temp_config):
        """重复设置覆盖旧值"""
        temp_config.set("key", "v1")
        temp_config.set("key", "v2")
        assert temp_config.get("key") == "v2"

    def test_set_different_keys_independent(self, temp_config):
        """不同 key 互相独立"""
        temp_config.set("a", 1)
        temp_config.set("b", 2)
        assert temp_config.get("a") == 1
        assert temp_config.get("b") == 2

    def test_none_is_valid_value(self, temp_config):
        """None 是合法的配置值"""
        temp_config.set("key", None)
        assert temp_config.get("key") is None


class TestMemoryConfigWatch:
    """配置变更监听测试"""

    def test_watch_receives_initial_set(self, temp_config):
        """监听器收到首次 set 通知"""
        tracker = CallbackTracker()
        temp_config.watch("test.*", tracker)

        temp_config.set("test.key", "value")

        assert tracker.call_count == 1
        assert tracker.last_call[0] == ("test.key", "value")

    def test_watch_receives_update(self, temp_config):
        """监听器收到值变更通知"""
        temp_config.set("test.key", "v1")

        tracker = CallbackTracker()
        temp_config.watch("test.*", tracker)

        temp_config.set("test.key", "v2")
        assert tracker.call_count == 1

    def test_watch_no_trigger_on_same_value(self, temp_config):
        """相同值不触发通知"""
        temp_config.set("test.key", "v1")

        tracker = CallbackTracker()
        temp_config.watch("test.*", tracker)

        temp_config.set("test.key", "v1")  # 相同值
        assert tracker.call_count == 0

    def test_watch_pattern_matching(self, temp_config):
        """fnmatch 模式匹配正确"""
        tracker = CallbackTracker()
        temp_config.watch("sensor.*", tracker)

        temp_config.set("sensor.temp", 25)
        temp_config.set("sensor.humidity", 60)
        temp_config.set("actuator.light", "on")  # 不匹配

        assert tracker.call_count == 2

    def test_unwatch_stops_callbacks(self, temp_config):
        """取消监听后不再收到通知"""
        tracker = CallbackTracker()
        watch_id = temp_config.watch("test.*", tracker)

        temp_config.set("test.a", 1)
        assert tracker.call_count == 1

        temp_config.unwatch(watch_id)

        temp_config.set("test.b", 2)
        assert tracker.call_count == 1  # 没有新增调用

    def test_unwatch_nonexistent_is_safe(self, temp_config):
        """取消不存在的 watch_id 不会报错"""
        temp_config.unwatch("nonexistent-watch-id")  # 不应抛出异常

    def test_watcher_exception_silently_ignored(self, temp_config):
        """监听器抛出异常不影响主流程"""
        def bad_callback(key, value):
            raise RuntimeError("Callback failed")

        temp_config.watch("test.*", bad_callback)
        temp_config.set("test.key", "value")  # 不应抛出异常

    def test_multiple_watchers_independent(self, temp_config):
        """多个监听器独立工作"""
        tracker1 = CallbackTracker()
        tracker2 = CallbackTracker()

        temp_config.watch("a.*", tracker1)
        temp_config.watch("b.*", tracker2)

        temp_config.set("a.x", 1)
        temp_config.set("b.y", 2)

        assert tracker1.call_count == 1
        assert tracker2.call_count == 1


class TestMemoryConfigNamespace:
    """命名空间测试"""

    def test_get_namespace_creates_child(self, temp_config):
        """获取命名空间创建子配置实例"""
        ns_config = temp_config.get_namespace("pluginA")
        assert ns_config is not None

    def test_namespaced_config_shares_data(self, temp_config):
        """命名空间配置共享底层数据"""
        ns_config = temp_config.get_namespace("pluginA")

        # 通过命名空间设置
        ns_config.set("timeout", 30)

        # 原始配置可以通过完整 key 读取
        assert temp_config.get("pluginA.timeout") == 30

        # 命名空间自动加前缀
        assert ns_config.get("timeout") == 30

    def test_namespace_watch_pattern_prefixed(self, temp_config):
        """命名空间下的 watch 模式自动加前缀"""
        ns_config = temp_config.get_namespace("pluginA")
        tracker = CallbackTracker()

        ns_config.watch("*", tracker)  # 实际监听 pluginA.*

        ns_config.set("x", 1)  # 触发
        temp_config.set("pluginA.y", 2)  # 也触发
        temp_config.set("other.z", 3)  # 不触发

        assert tracker.call_count == 2

    def test_namespace_watchers_shared(self, temp_config):
        """命名空间配置共享 watchers 字典"""
        ns1 = temp_config.get_namespace("ns1")
        ns2 = temp_config.get_namespace("ns2")

        assert ns1._watchers is ns2._watchers
        assert ns1._watchers is temp_config._watchers


class TestMemoryConfigBulkLoad:
    """批量加载测试"""

    def test_bulk_load_multiple_keys(self, temp_config):
        """批量加载多个配置项"""
        configs = {
            "db.host": "localhost",
            "db.port": 5432,
            "api.timeout": 30,
        }

        temp_config.bulk_load(configs)

        assert temp_config.get("db.host") == "localhost"
        assert temp_config.get("db.port") == 5432
        assert temp_config.get("api.timeout") == 30

    def test_bulk_load_triggers_watchers(self, temp_config):
        """批量加载也触发监听器"""
        tracker = CallbackTracker()
        temp_config.watch("db.*", tracker)

        temp_config.bulk_load({
            "db.host": "localhost",
            "db.port": 5432,
            "api.key": "secret",
        })

        assert tracker.call_count == 2  # 只匹配 db.*
