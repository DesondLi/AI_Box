"""
LLM 引擎接口定义

统一不同 LLM 提供商的调用接口，支持热插拔切换
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import List, Dict, Optional, Any, AsyncIterable, Tuple


class ChatRole(Enum):
    """对话角色"""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class ChatMessage:
    """对话消息"""
    role: ChatRole
    content: str
    name: Optional[str] = None
    tool_call_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {"role": self.role.value, "content": self.content}
        if self.name:
            result["name"] = self.name
        return result


@dataclass
class CompletionUsage:
    """Token 用量统计"""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

    @classmethod
    def zero(cls) -> 'CompletionUsage':
        return cls(0, 0, 0)

    def __add__(self, other: 'CompletionUsage') -> 'CompletionUsage':
        return CompletionUsage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
        )


@dataclass
class CompletionResult:
    """补全结果"""
    content: str
    model: str
    usage: CompletionUsage
    finish_reason: Optional[str] = None
    raw_response: Any = None


@dataclass
class EmbeddingResult:
    """嵌入结果"""
    embedding: List[float]
    model: str
    usage: CompletionUsage


@dataclass
class ModelInfo:
    """模型信息"""
    model_id: str
    name: str
    max_tokens: int
    supports_streaming: bool = False
    supports_tools: bool = False
    cost_per_1k_prompt: float = 0.0  # USD
    cost_per_1k_completion: float = 0.0


class ILLMCompletion(ABC):
    """文本补全接口"""

    @abstractmethod
    async def complete(
        self,
        prompt: str,
        max_tokens: int = 512,
        temperature: float = 0.7,
        **kwargs,
    ) -> CompletionResult:
        """
        文本补全

        Args:
            prompt: 提示词
            max_tokens: 最大生成长度
            temperature: 采样温度 (0-1)
            **kwargs: 模型特定参数

        Returns:
            补全结果
        """
        pass


class ILLMChat(ABC):
    """对话补全接口"""

    @abstractmethod
    async def chat(
        self,
        messages: List[ChatMessage],
        max_tokens: int = 1024,
        temperature: float = 0.7,
        **kwargs,
    ) -> CompletionResult:
        """
        对话补全

        Args:
            messages: 对话历史
            max_tokens: 最大生成长度
            temperature: 采样温度 (0-1)
            **kwargs: 模型特定参数

        Returns:
            对话结果
        """
        pass

    async def chat_stream(
        self,
        messages: List[ChatMessage],
        max_tokens: int = 1024,
        temperature: float = 0.7,
        **kwargs,
    ) -> AsyncIterable[str]:
        """
        流式对话（可选实现）

        Args:
            messages: 对话历史
            max_tokens: 最大生成长度
            temperature: 采样温度

        Yields:
            内容片段
        """
        raise NotImplementedError("Streaming not supported by this adapter")


class ILLMEmbedding(ABC):
    """向量嵌入接口"""

    @abstractmethod
    async def embed(
        self,
        text: str,
        **kwargs,
    ) -> EmbeddingResult:
        """
        生成文本嵌入向量

        Args:
            text: 待嵌入文本
            **kwargs: 模型特定参数

        Returns:
            嵌入结果
        """
        pass

    async def embed_batch(
        self,
        texts: List[str],
        **kwargs,
    ) -> List[EmbeddingResult]:
        """
        批量生成嵌入向量（默认逐个调用，适配器可优化）

        Args:
            texts: 文本列表

        Returns:
            嵌入结果列表
        """
        results = []
        for text in texts:
            results.append(await self.embed(text, **kwargs))
        return results


class ILLMCostTracker(ABC):
    """成本追踪器接口"""

    @abstractmethod
    def record_usage(self, model: str, usage: CompletionUsage) -> None:
        """
        记录 Token 用量

        Args:
            model: 模型 ID
            usage: 用量统计
        """
        pass

    @abstractmethod
    def get_total_cost(self, since: Optional[datetime] = None) -> float:
        """
        获取累计成本

        Args:
            since: 可选，统计从指定时间开始的成本

        Returns:
            总成本（USD）
        """
        pass

    @abstractmethod
    def get_usage_by_model(self, since: Optional[datetime] = None) -> Dict[str, CompletionUsage]:
        """
        按模型获取用量统计

        Returns:
            {model_id: usage} 字典
        """
        pass
