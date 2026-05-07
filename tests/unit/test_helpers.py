"""
测试辅助工具和通用 Mock 类
"""
from typing import List, Any
from kernel.interfaces import IPlugin, IKernelContext


class LifecycleTracker:
    """跟踪插件生命周期调用"""
    def __init__(self):
        self.events: List[str] = []

    def record(self, event: str):
        self.events.append(event)


class MockPlugin(IPlugin):
    """通用 Mock 插件

    支持：
    - 自定义依赖列表
    - 在指定阶段抛出异常（install/start/stop）
    - 记录生命周期调用
    """
    def __init__(self, plugin_id: str, deps: list = None, fail_at: str = None):
        self._plugin_id = plugin_id
        self._deps = deps or []
        self.fail_at = fail_at  # 'install' / 'start' / 'stop' / None
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


class CallbackTracker:
    """跟踪回调函数调用次数和参数"""
    def __init__(self):
        self.calls: List[tuple] = []

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))

    @property
    def call_count(self) -> int:
        return len(self.calls)

    @property
    def last_call(self) -> tuple:
        return self.calls[-1] if self.calls else None
