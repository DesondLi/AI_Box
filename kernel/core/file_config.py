"""
文件配置注册表实现

支持：
- JSON/YAML 序列化到磁盘
- 文件变更自动热重载
- 命名空间隔离
- watcher 通知机制
"""

import asyncio
import json
import os
import uuid
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    yaml = None
    YAML_AVAILABLE = False

from ..interfaces import IConfigRegistry


class FileConfigRegistry(IConfigRegistry):
    """基于文件的配置注册表，支持持久化与热重载"""

    def __init__(
        self,
        namespace: str = "",
        file_path: Optional[str] = None,
        file_format: str = "json",  # json 或 yaml
        auto_save: bool = True,
    ):
        self._data: Dict[str, Any] = {}
        self._watchers: Dict[str, Tuple[str, Callable]] = {}
        self._namespace = namespace
        self._file_path = file_path
        self._file_format = file_format.lower()
        self._auto_save = auto_save

        # 热重载相关
        self._hotreload_task: Optional[asyncio.Task] = None
        self._hotreload_running: bool = False
        self._last_mtime: float = 0.0

        # 命名空间共享状态引用（子配置共享父配置的数据和 watcher）
        self._shared_data: Optional[Dict[str, Any]] = None
        self._shared_watchers: Optional[Dict[str, Tuple[str, Callable]]] = None

    def _make_key(self, key: str) -> str:
        """构造带命名空间的 key"""
        if not self._namespace:
            return key
        return f"{self._namespace}.{key}"

    def _get_data(self) -> Dict[str, Any]:
        """获取实际数据字典（可能来自共享）"""
        return self._shared_data if self._shared_data is not None else self._data

    def _get_watchers(self) -> Dict[str, Tuple[str, Callable]]:
        """获取实际 watcher 字典（可能来自共享）"""
        return self._shared_watchers if self._shared_watchers is not None else self._watchers

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        full_key = self._make_key(key)
        return self._get_data().get(full_key, default)

    def set(self, key: str, value: Any) -> None:
        """设置配置值（触发变更通知 + 自动保存）"""
        full_key = self._make_key(key)
        data = self._get_data()
        old_value = data.get(full_key)

        if old_value == value:
            return  # 无变化，不触发通知

        data[full_key] = value

        # 触发所有匹配的 watcher（包括所有命名空间的）
        watchers = self._get_watchers()
        for watch_id, (pattern, callback) in watchers.items():
            if fnmatch(full_key, pattern):
                try:
                    callback(full_key, value)
                except Exception:
                    pass  # watcher 异常不影响主流程

        # 自动保存
        if self._auto_save and self._file_path:
            self.save()

    def watch(self, key_pattern: str, callback: Callable[[str, Any], None]) -> str:
        """监听配置变更"""
        watch_id = f"watch-{uuid.uuid4().hex[:8]}"
        full_pattern = self._make_key(key_pattern)
        self._get_watchers()[watch_id] = (full_pattern, callback)
        return watch_id

    def unwatch(self, watch_id: str) -> None:
        """取消配置监听"""
        self._get_watchers().pop(watch_id, None)

    def get_namespace(self, namespace: str) -> 'FileConfigRegistry':
        """获取命名空间下的子配置，共享数据和 watcher"""
        child_ns = f"{self._namespace}.{namespace}" if self._namespace else namespace
        child = FileConfigRegistry(child_ns, self._file_path, self._file_format, self._auto_save)

        # 子配置共享父配置的数据和 watcher 字典
        child._shared_data = self._get_data()
        child._shared_watchers = self._get_watchers()

        return child

    # --- 持久化实现 ---

    def save(self, path: Optional[str] = None) -> None:
        """保存配置到文件"""
        target_path = path or self._file_path
        if not target_path:
            raise ValueError("No file path specified and no default path set")

        target_path = str(target_path)
        data = self._get_data()

        # 只保存顶级命名空间的内容（避免子配置重复保存）
        # 实际应该所有层级都保存到同一文件，这里直接保存整个字典
        os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)

        if self._file_format == "json":
            with open(target_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        elif self._file_format in ("yaml", "yml"):
            if not YAML_AVAILABLE:
                raise ImportError("PyYAML not installed, install with: pip install pyyaml")
            with open(target_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(data, f, allow_unicode=True, default_flow_style=False)
        else:
            raise ValueError(f"Unsupported format: {self._file_format}")

        # 更新 mtime 防止立即触发热重载
        self._last_mtime = os.path.getmtime(target_path)

    def load(self, path: Optional[str] = None) -> None:
        """从文件加载配置"""
        target_path = path or self._file_path
        if not target_path:
            raise ValueError("No file path specified and no default path set")

        target_path = str(target_path)
        data = self._get_data()

        if not os.path.exists(target_path):
            # 文件不存在，清空配置（但不删除 watcher）
            data.clear()
            return

        if self._file_format == "json":
            with open(target_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
        elif self._file_format in ("yaml", "yml"):
            if not YAML_AVAILABLE:
                raise ImportError("PyYAML not installed, install with: pip install pyyaml")
            with open(target_path, "r", encoding="utf-8") as f:
                loaded = yaml.safe_load(f) or {}
        else:
            raise ValueError(f"Unsupported format: {self._file_format}")

        if not isinstance(loaded, dict):
            raise ValueError(f"Config file must contain a dictionary, got {type(loaded)}")

        # 检测变更并触发 watcher
        watchers = self._get_watchers()

        for key, new_value in loaded.items():
            old_value = data.get(key)
            if old_value != new_value:
                data[key] = new_value
                # 触发 watcher
                for watch_id, (pattern, callback) in watchers.items():
                    if fnmatch(key, pattern):
                        try:
                            callback(key, new_value)
                        except Exception:
                            pass

        # 删除文件中不存在的 key
        for key in list(data.keys()):
            if key not in loaded:
                del data[key]

        # 更新 mtime
        self._last_mtime = os.path.getmtime(target_path)

    # --- 热重载实现 ---

    def enable_hotreload(self, path: Optional[str] = None, interval: float = 1.0) -> None:
        """启用热重载，自动监听文件变更"""
        if self._hotreload_running:
            return

        target_path = path or self._file_path
        if not target_path:
            raise ValueError("No file path specified and no default path set")

        self._file_path = target_path
        self._hotreload_running = True

        # 如果文件已存在，先加载并记录 mtime
        if os.path.exists(target_path):
            self._last_mtime = os.path.getmtime(target_path)

        # 启动后台监听任务
        loop = asyncio.get_event_loop_policy().get_event_loop()
        self._hotreload_task = loop.create_task(self._hotreload_worker(interval))

    def disable_hotreload(self) -> None:
        """禁用热重载"""
        self._hotreload_running = False
        if self._hotreload_task and not self._hotreload_task.done():
            self._hotreload_task.cancel()
        self._hotreload_task = None

    @property
    def has_hotreload(self) -> bool:
        """是否启用了热重载"""
        return self._hotreload_running

    async def _hotreload_worker(self, interval: float):
        """热重载后台工作协程"""
        while self._hotreload_running:
            try:
                if self._file_path and os.path.exists(self._file_path):
                    current_mtime = os.path.getmtime(self._file_path)
                    if current_mtime > self._last_mtime:
                        self.load(self._file_path)
            except asyncio.CancelledError:
                break
            except Exception:
                # 静默处理文件访问错误（可能被锁定、正在写入等）
                pass

            await asyncio.sleep(interval)

    # --- 便捷方法 ---

    def bulk_load(self, config_dict: Dict[str, Any]) -> None:
        """批量加载配置（内存方式，不写入文件）"""
        for key, value in config_dict.items():
            self.set(key, value)

    def as_dict(self) -> Dict[str, Any]:
        """获取所有配置的字典副本"""
        return dict(self._get_data())

    def clear(self) -> None:
        """清空所有配置（只清空内存，不清空文件）"""
        self._get_data().clear()

    def get_file_path(self) -> Optional[str]:
        """获取当前配置文件路径"""
        return self._file_path
