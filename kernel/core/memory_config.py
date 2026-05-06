"""
内存配置注册表实现

支持：
- KV 存储
- 热重载 watch 机制
- 命名空间
"""

import uuid
from typing import Any, Callable, Dict
from fnmatch import fnmatch

from kernel.interfaces import IConfigRegistry


class MemoryConfigRegistry(IConfigRegistry):
    """基于内存的配置注册表"""

    def __init__(self, namespace: str = ""):
        self._data: Dict[str, Any] = {}
        self._watchers: Dict[str, Tuple[str, Callable]] = {}
        self._namespace = namespace

    def _make_key(self, key: str) -> str:
        """构造带命名空间的key"""
        if not self._namespace:
            return key
        return f"{self._namespace}.{key}"

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        return self._data.get(self._make_key(key), default)

    def set(self, key: str, value: Any) -> None:
        """设置配置值（触发变更通知）"""
        full_key = self._make_key(key)
        old_value = self._data.get(full_key)
        self._data[full_key] = value

        # 触发所有匹配的 watcher
        if old_value != value:
            for watch_id, (pattern, callback) in self._watchers.items():
                if fnmatch(full_key, pattern):
                    try:
                        callback(full_key, value)
                    except Exception:
                        pass  # watcher 异常不影响主流程

    def watch(self, key_pattern: str, callback: Callable[[str, Any], None]) -> str:
        """监听配置变更"""
        watch_id = f"watch-{uuid.uuid4().hex[:8]}"
        full_pattern = self._make_key(key_pattern)
        self._watchers[watch_id] = (full_pattern, callback)
        return watch_id

    def unwatch(self, watch_id: str) -> None:
        """取消配置监听"""
        self._watchers.pop(watch_id, None)

    def get_namespace(self, namespace: str) -> 'MemoryConfigRegistry':
        """获取命名空间下的子配置"""
        child_ns = f"{self._namespace}.{namespace}" if self._namespace else namespace
        child = MemoryConfigRegistry(child_ns)
        child._data = self._data  # 共享同一个数据字典
        child._watchers = self._watchers  # 共享监听器
        return child

    def bulk_load(self, config_dict: Dict[str, Any]) -> None:
        """批量加载配置"""
        for key, value in config_dict.items():
            self.set(key, value)
