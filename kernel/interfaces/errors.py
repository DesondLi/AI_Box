"""
统一错误处理定义
"""

from dataclasses import dataclass
from enum import IntEnum
from typing import Optional, Dict, TypeVar, Union, Generic

T = TypeVar('T')
Result = Union[T, 'PluginError']  # 简化定义，避免PEP 695语法问题


class ErrorLevel(IntEnum):
    """错误严重级别"""
    DEBUG = 0       # 调试信息，不影响运行
    WARNING = 1     # 警告，可自动恢复
    ERROR = 2       # 错误，需人工介入但系统仍可运行
    CRITICAL = 3    # 致命，系统必须停止或重启


@dataclass
class PluginError:
    """标准错误对象，所有插件必须返回此类型"""
    code: str                      # 错误码，见规范
    message: str                   # 人类可读描述
    level: ErrorLevel              # 严重级别
    plugin_id: str                 # 产生错误的插件ID
    timestamp: int                 # 发生时间戳 ms
    retryable: bool = False        # 是否可重试
    cause: Optional[str] = None    # 根因错误（异常堆栈字符串）
    context: Dict[str, str] = None # 上下文信息

    @classmethod
    def from_exception(cls, plugin_id: str, e: Exception,
                      level: ErrorLevel = ErrorLevel.ERROR) -> 'PluginError':
        import traceback
        import time
        return cls(
            code="E-PLUGIN-EXCEPTION",
            message=str(e),
            level=level,
            plugin_id=plugin_id,
            timestamp=int(time.time() * 1000),
            cause=traceback.format_exc(),
        )

    def is_error(self) -> bool:
        return True
