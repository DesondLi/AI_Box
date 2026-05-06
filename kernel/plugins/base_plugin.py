"""
插件基类：提供默认实现，减少样板代码

新插件建议继承此类，只需要重写需要的方法
"""

from typing import Dict, Any, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..interfaces import IKernelContext, IPluginLogger, IConfigRegistry, IMessageBus

from ..interfaces import IPlugin


class BasePlugin(IPlugin):
    """插件基类：提供默认空实现"""

    def __init__(self):
        self._context: Optional['IKernelContext'] = None
        self._logger: Optional['IPluginLogger'] = None
        self._config: Optional['IConfigRegistry'] = None
        self._message_bus: Optional['IMessageBus'] = None

    @property
    def plugin_id(self) -> str:
        """默认使用类名转小写"""
        return self.__class__.__name__.lower().replace("plugin", "")

    @property
    def version(self) -> str:
        return "0.1.0"

    @property
    def dependencies(self) -> List[str]:
        """默认无依赖"""
        return []

    async def install(self, context: 'IKernelContext') -> None:
        """默认安装：保存上下文引用"""
        self._context = context
        self._logger = context.logger.for_plugin(self.plugin_id)
        self._config = context.config.get_namespace(self.plugin_id)
        self._message_bus = context.message_bus

        self._logger.debug(f"Installed, dependencies: {self.dependencies}")

    async def start(self) -> None:
        """默认启动：空实现"""
        if self._logger:
            self._logger.debug("Started")

    async def stop(self) -> None:
        """默认停止：空实现"""
        if self._logger:
            self._logger.debug("Stopped")

    async def uninstall(self) -> None:
        """默认卸载：空实现"""
        pass

    def get_capabilities(self) -> Dict[str, Any]:
        """默认无能力"""
        return {}

    # --- 便捷方法 ---

    def log_debug(self, msg: str, **kwargs) -> None:
        if self._logger:
            self._logger.debug(msg, **kwargs)

    def log_info(self, msg: str, **kwargs) -> None:
        if self._logger:
            self._logger.info(msg, **kwargs)

    def log_warn(self, msg: str, **kwargs) -> None:
        if self._logger:
            self._logger.warn(msg, **kwargs)

    def log_error(self, msg: str, e: Exception = None, **kwargs) -> None:
        if self._logger:
            self._logger.error(msg, e, **kwargs)

    def cfg(self, key: str, default: Any = None) -> Any:
        """获取本插件命名空间下的配置"""
        if self._config:
            return self._config.get(key, default)
        return default
