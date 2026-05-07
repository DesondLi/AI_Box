"""
核心接口定义

所有插件只依赖这个包，不直接依赖内核实现
依赖倒置原则：抽象不依赖细节，细节依赖抽象
"""

from .plugin import IPlugin, PluginLifeCycle
from .kernel_context import IKernelContext
from .message_bus import IMessageBus
from .config import IConfigRegistry
from .logger import ILoggerFactory, IPluginLogger
from .errors import PluginError, ErrorLevel, Result
from .rag import (
    ITimeseriesSemanticBridge,
    TimeSeriesPoint,
    SemanticDocument,
    RetrievalResult,
    TrendType,
    AnomalySeverity,
)
from .llm import (
    ILLMCompletion,
    ILLMChat,
    ILLMEmbedding,
    ILLMCostTracker,
    ChatRole,
    ChatMessage,
    CompletionUsage,
    CompletionResult,
    EmbeddingResult,
    ModelInfo,
)

__all__ = [
    "IPlugin",
    "PluginLifeCycle",
    "IKernelContext",
    "IMessageBus",
    "IConfigRegistry",
    "ILoggerFactory",
    "IPluginLogger",
    "PluginError",
    "ErrorLevel",
    "Result",
    "ITimeseriesSemanticBridge",
    "TimeSeriesPoint",
    "SemanticDocument",
    "RetrievalResult",
    "TrendType",
    "AnomalySeverity",
    # LLM Engine
    "ILLMCompletion",
    "ILLMChat",
    "ILLMEmbedding",
    "ILLMCostTracker",
    "ChatRole",
    "ChatMessage",
    "CompletionUsage",
    "CompletionResult",
    "EmbeddingResult",
    "ModelInfo",
]
