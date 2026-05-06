"""
控制台日志实现

支持：
- 结构化字段
- 颜色输出
- 插件隔离
"""

import time
from typing import Any, Dict
from colorama import Fore, Style, init

from kernel.interfaces import ILoggerFactory, IPluginLogger, ErrorLevel

# 初始化 colorama
init(autoreset=True)


class ConsoleLogger(IPluginLogger):
    """控制台日志实现"""

    _LEVEL_COLORS = {
        ErrorLevel.DEBUG: Fore.CYAN,
        ErrorLevel.WARNING: Fore.YELLOW,
        ErrorLevel.ERROR: Fore.RED,
        ErrorLevel.CRITICAL: Fore.MAGENTA,
    }

    _LEVEL_NAMES = {
        ErrorLevel.DEBUG: "DEBUG",
        ErrorLevel.WARNING: "WARN",
        ErrorLevel.ERROR: "ERROR",
        ErrorLevel.CRITICAL: "CRIT",
    }

    def __init__(self, plugin_id: str, fields: Dict[str, str] = None):
        self._plugin_id = plugin_id
        self._fields = fields or {}

    def _format(self, level: ErrorLevel, message: str, **kwargs: Any) -> str:
        """格式化日志行"""
        ts = time.strftime("%H:%M:%S")
        color = self._LEVEL_COLORS.get(level, "")
        level_name = self._LEVEL_NAMES.get(level, "INFO")

        # 合并字段
        all_fields = {**self._fields, **kwargs}
        fields_str = " ".join(f"{k}={v}" for k, v in all_fields.items())

        if fields_str:
            return f"{ts} {color}[{level_name:5}] {self._plugin_id:15} {message} {Fore.LIGHTBLACK_EX}{fields_str}"
        return f"{ts} {color}[{level_name:5}] {self._plugin_id:15} {message}"

    def debug(self, message: str, **kwargs: Any) -> None:
        print(self._format(ErrorLevel.DEBUG, message, **kwargs))

    def info(self, message: str, **kwargs: Any) -> None:
        print(self._format(ErrorLevel.WARNING, message, **kwargs))  # 用 WARNING 颜色区分

    def warn(self, message: str, **kwargs: Any) -> None:
        print(self._format(ErrorLevel.WARNING, message, **kwargs))

    def error(self, message: str, exception: Exception = None, **kwargs: Any) -> None:
        if exception:
            message = f"{message}: {exception}"
        print(self._format(ErrorLevel.ERROR, message, **kwargs))

    def with_fields(self, **fields: str) -> 'ConsoleLogger':
        """创建带上下文字段的子日志实例"""
        return ConsoleLogger(self._plugin_id, {**self._fields, **fields})


class ConsoleLoggerFactory(ILoggerFactory):
    """控制台日志工厂"""

    def for_plugin(self, plugin_id: str) -> ConsoleLogger:
        return ConsoleLogger(plugin_id)
