"""
插件注册表：管理所有已加载的插件
"""

import asyncio
from typing import Dict, List, Optional, Set
from dataclasses import dataclass

from kernel.interfaces import IPlugin, PluginLifeCycle, IKernelContext


@dataclass
class PluginEntry:
    """插件注册表条目"""
    plugin: IPlugin
    state: PluginLifeCycle
    context: Optional['IKernelContext'] = None


class PluginRegistry:
    """插件注册表"""

    def __init__(self):
        self._plugins: Dict[str, PluginEntry] = {}
        self._capabilities: Dict[str, object] = {}

    def register(self, plugin: IPlugin) -> None:
        """注册插件"""
        if plugin.plugin_id in self._plugins:
            raise ValueError(f"Plugin {plugin.plugin_id} already registered")
        self._plugins[plugin.plugin_id] = PluginEntry(
            plugin=plugin,
            state=PluginLifeCycle.CREATED,
        )

    def get(self, plugin_id: str) -> Optional[IPlugin]:
        """获取插件实例"""
        entry = self._plugins.get(plugin_id)
        return entry.plugin if entry else None

    def get_entry(self, plugin_id: str) -> Optional[PluginEntry]:
        """获取插件完整条目"""
        return self._plugins.get(plugin_id)

    def set_state(self, plugin_id: str, state: PluginLifeCycle) -> None:
        """更新插件状态"""
        entry = self._plugins.get(plugin_id)
        if entry:
            entry.state = state

    def get_state(self, plugin_id: str) -> Optional[PluginLifeCycle]:
        """获取插件状态"""
        entry = self._plugins.get(plugin_id)
        return entry.state if entry else None

    def list_all(self) -> List[str]:
        """列出所有插件ID"""
        return list(self._plugins.keys())

    def register_capability(self, capability: str, provider: object) -> None:
        """注册能力"""
        self._capabilities[capability] = provider

    def get_capability(self, capability: str) -> Optional[object]:
        """获取能力提供者"""
        return self._capabilities.get(capability)

    def resolve_dependencies(self) -> List[str]:
        """
        解析依赖关系，返回正确的启动顺序
        使用拓扑排序
        """
        # 构建依赖图
        graph: Dict[str, Set[str]] = {}
        for pid, entry in self._plugins.items():
            graph[pid] = set(entry.plugin.dependencies)

        # 拓扑排序
        result = []
        visited = set()
        temp = set()

        def visit(node: str):
            if node in temp:
                raise ValueError(f"Circular dependency detected at {node}")
            if node in visited:
                return
            temp.add(node)
            for dep in graph.get(node, set()):
                if dep in self._plugins:  # 只考虑已注册的插件
                    visit(dep)
            temp.remove(node)
            visited.add(node)
            result.append(node)

        for pid in self._plugins:
            if pid not in visited:
                visit(pid)

        return result
