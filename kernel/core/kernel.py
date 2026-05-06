"""
微内核核心实现

这是整个系统的唯一入口，负责：
1. 管理所有核心服务（配置、日志、消息总线）
2. 插件生命周期管理
3. 依赖注入
"""

import asyncio
from typing import Optional, Any

from kernel.interfaces import (
    IPlugin, IKernelContext, IConfigRegistry, ILoggerFactory, IMessageBus,
    PluginLifeCycle,
)
from kernel.core.plugin_registry import PluginRegistry
from kernel.core.memory_message_bus import MemoryMessageBus
from kernel.core.memory_config import MemoryConfigRegistry
from kernel.core.console_logger import ConsoleLoggerFactory


class KernelContext(IKernelContext):
    """内核上下文实现"""

    def __init__(self, kernel: 'MicroKernel', plugin_id: str):
        self._kernel = kernel
        self._plugin_id = plugin_id
        self._logger = kernel.logger.for_plugin(plugin_id)

    @property
    def config(self) -> IConfigRegistry:
        return self._kernel.config

    @property
    def logger(self) -> ILoggerFactory:
        return self._kernel.logger

    @property
    def message_bus(self) -> IMessageBus:
        return self._kernel.message_bus

    def get_plugin(self, plugin_id: str) -> Optional[IPlugin]:
        return self._kernel.plugin_registry.get(plugin_id)

    def register_capability(self, capability: str, provider: Any) -> None:
        self._kernel.plugin_registry.register_capability(capability, provider)

    def get_capability(self, capability: str) -> Optional[Any]:
        return self._kernel.plugin_registry.get_capability(capability)


class MicroKernel:
    """微内核核心"""

    def __init__(self):
        self._plugin_registry = PluginRegistry()
        self._config = MemoryConfigRegistry()
        self._logger_factory = ConsoleLoggerFactory()
        self._message_bus = MemoryMessageBus()
        self._logger = self._logger_factory.for_plugin("kernel")
        self._running = False

    @property
    def plugin_registry(self) -> PluginRegistry:
        return self._plugin_registry

    @property
    def config(self) -> IConfigRegistry:
        return self._config

    @property
    def logger(self) -> ILoggerFactory:
        return self._logger_factory

    @property
    def message_bus(self) -> IMessageBus:
        return self._message_bus

    def register_plugin(self, plugin: IPlugin) -> None:
        """注册插件"""
        self._plugin_registry.register(plugin)
        self._logger.info(f"Plugin registered: {plugin.plugin_id} v{plugin.version}")

    def create_context(self, plugin_id: str) -> IKernelContext:
        """为插件创建上下文"""
        return KernelContext(self, plugin_id)

    async def start(self) -> None:
        """启动内核和所有已注册的插件"""
        if self._running:
            self._logger.warn("Kernel already running, ignoring start request")
            return

        self._logger.info("=" * 60)
        self._logger.info("MicroKernel starting...")
        self._logger.info(f"Registered plugins: {len(self._plugin_registry.list_all())}")

        # 解析依赖顺序
        start_order = self._plugin_registry.resolve_dependencies()
        self._logger.info(f"Startup order: {start_order}")

        # 阶段1：安装所有插件
        self._logger.info("--- Phase 1: Installing plugins ---")
        for plugin_id in start_order:
            entry = self._plugin_registry.get_entry(plugin_id)
            if not entry:
                continue

            try:
                self._plugin_registry.set_state(plugin_id, PluginLifeCycle.INSTALLING)
                context = self.create_context(plugin_id)
                entry.context = context

                await entry.plugin.install(context)
                self._plugin_registry.set_state(plugin_id, PluginLifeCycle.INSTALLED)
                self._logger.info(f"[OK] {plugin_id}: installed")

            except Exception as e:
                self._plugin_registry.set_state(plugin_id, PluginLifeCycle.ERROR)
                self._logger.error(f"[ERR] {plugin_id}: install failed", exception=e)
                raise

        # 阶段2：启动所有插件
        self._logger.info("--- Phase 2: Starting plugins ---")
        for plugin_id in start_order:
            entry = self._plugin_registry.get_entry(plugin_id)
            if not entry or entry.state != PluginLifeCycle.INSTALLED:
                continue

            try:
                self._plugin_registry.set_state(plugin_id, PluginLifeCycle.STARTING)
                await entry.plugin.start()
                self._plugin_registry.set_state(plugin_id, PluginLifeCycle.RUNNING)
                self._logger.info(f"[OK] {plugin_id}: running")

            except Exception as e:
                self._plugin_registry.set_state(plugin_id, PluginLifeCycle.ERROR)
                self._logger.error(f"[ERR] {plugin_id}: start failed", exception=e)
                raise

        self._running = True
        self._logger.info("=" * 60)
        self._logger.info("MicroKernel started successfully!")

    async def stop(self) -> None:
        """停止内核和所有插件"""
        if not self._running:
            return

        self._logger.info("MicroKernel stopping...")

        # 逆序停止（依赖方先停）
        stop_order = reversed(self._plugin_registry.resolve_dependencies())

        for plugin_id in stop_order:
            entry = self._plugin_registry.get_entry(plugin_id)
            if not entry or entry.state != PluginLifeCycle.RUNNING:
                continue

            try:
                self._plugin_registry.set_state(plugin_id, PluginLifeCycle.STOPPING)
                await entry.plugin.stop()
                self._plugin_registry.set_state(plugin_id, PluginLifeCycle.STOPPED)
                self._logger.info(f"[OK] {plugin_id}: stopped")
            except Exception as e:
                self._logger.error(f"[ERR] {plugin_id}: stop failed", exception=e)

        self._running = False
        self._logger.info("MicroKernel stopped")
