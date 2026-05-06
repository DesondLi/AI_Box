"""
插件生命周期接口定义
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .kernel_context import IKernelContext


class PluginLifeCycle(Enum):
    """插件生命周期状态"""
    CREATED = "created"        # 已创建，未安装
    INSTALLING = "installing"  # 正在安装
    INSTALLED = "installed"    # 已安装，未启动
    STARTING = "starting"      # 正在启动
    RUNNING = "running"        # 正常运行
    STOPPING = "stopping"      # 正在停止
    STOPPED = "stopped"        # 已停止
    ERROR = "error"            # 出错状态


class IPlugin(ABC):
    """所有插件必须实现的基础接口"""

    @property
    @abstractmethod
    def plugin_id(self) -> str:
        """唯一插件ID: 反向域名风格, e.g. 'io.mqtt.v3' """
        pass

    @property
    @abstractmethod
    def version(self) -> str:
        """语义化版本: e.g. '1.2.3' """
        pass

    @property
    @abstractmethod
    def dependencies(self) -> list[str]:
        """依赖的其他插件ID列表: ['kernel.config', 'kernel.logger']"""
        pass

    @abstractmethod
    async def install(self, context: 'IKernelContext') -> None:
        """安装阶段：注册配置、声明能力、不启动资源"""
        pass

    @abstractmethod
    async def start(self) -> None:
        """启动阶段：初始化连接、启动后台任务"""
        pass

    @abstractmethod
    async def stop(self) -> None:
        """停止阶段：优雅关闭、释放资源"""
        pass

    @abstractmethod
    async def uninstall(self) -> None:
        """卸载阶段：清理持久化数据"""
        pass

    def get_capabilities(self) -> Dict[str, Any]:
        """声明此插件提供的能力，供其他插件发现"""
        return {}
