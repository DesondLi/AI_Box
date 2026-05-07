"""
OpenAI 适配器插件

提供统一的 LLM 调用接口，支持：
- GPT-3.5/4 系列对话模型
- text-embedding-ada-002 嵌入模型
- 响应缓存减少重复请求
- Token 成本统计
- 自动重试与超时
"""

import asyncio
import hashlib
import json
from datetime import datetime
from typing import List, Dict, Optional, Any, AsyncIterable, Tuple
from dataclasses import dataclass, field

try:
    from openai import AsyncOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    AsyncOpenAI = None
    OPENAI_AVAILABLE = False

from ..interfaces import (
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
from .base_plugin import BasePlugin


@dataclass
class CacheEntry:
    """缓存条目"""
    result: CompletionResult
    timestamp: datetime
    hits: int = 0


class LRUCache:
    """简单 LRU 缓存

    基于有序字典实现，超过容量后移除最久未访问的条目
    """

    def __init__(self, capacity: int = 100, ttl_seconds: int = 3600):
        self.capacity = capacity
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, CacheEntry] = {}

    def _make_key(self, *args, **kwargs) -> str:
        """生成缓存键"""
        key_data = {"args": args, "kwargs": kwargs}
        key_json = json.dumps(key_data, sort_keys=True, default=str)
        return hashlib.md5(key_json.encode()).hexdigest()

    def get(self, *args, **kwargs) -> Optional[CompletionResult]:
        """获取缓存"""
        key = self._make_key(*args, **kwargs)
        entry = self._cache.get(key)
        if entry is None:
            return None

        # 检查 TTL
        age = (datetime.now() - entry.timestamp).total_seconds()
        if age > self.ttl_seconds:
            del self._cache[key]
            return None

        entry.hits += 1
        # 移到末尾表示最近访问
        del self._cache[key]
        self._cache[key] = entry
        return entry.result

    def put(self, result: CompletionResult, *args, **kwargs) -> None:
        """存入缓存"""
        key = self._make_key(*args, **kwargs)

        if key in self._cache:
            del self._cache[key]
        elif len(self._cache) >= self.capacity:
            # 移除最旧的（第一个）
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]

        self._cache[key] = CacheEntry(result=result, timestamp=datetime.now())

    @property
    def size(self) -> int:
        return len(self._cache)

    def clear(self) -> None:
        self._cache.clear()


class CostTracker(ILLMCostTracker):
    """Token 成本追踪器"""

    # 模型定价（USD / 1K tokens）
    # 参考：https://openai.com/pricing
    MODEL_PRICING = {
        "gpt-3.5-turbo": (0.0015, 0.002),
        "gpt-3.5-turbo-1106": (0.001, 0.002),
        "gpt-3.5-turbo-16k": (0.003, 0.004),
        "gpt-4": (0.03, 0.06),
        "gpt-4-32k": (0.06, 0.12),
        "gpt-4-1106-preview": (0.01, 0.03),
        "text-embedding-ada-002": (0.0001, 0.0),
    }

    def __init__(self):
        self._history: List[Tuple[datetime, str, CompletionUsage]] = []

    def record_usage(self, model: str, usage: CompletionUsage) -> None:
        self._history.append((datetime.now(), model, usage))

    def get_total_cost(self, since: Optional[datetime] = None) -> float:
        total = 0.0
        for ts, model, usage in self._history:
            if since and ts < since:
                continue
            prompt_cost, comp_cost = self.MODEL_PRICING.get(model, (0.0, 0.0))
            total += (usage.prompt_tokens / 1000 * prompt_cost) + \
                     (usage.completion_tokens / 1000 * comp_cost)
        return total

    def get_usage_by_model(self, since: Optional[datetime] = None) -> Dict[str, CompletionUsage]:
        result: Dict[str, CompletionUsage] = {}
        for ts, model, usage in self._history:
            if since and ts < since:
                continue
            if model not in result:
                result[model] = CompletionUsage.zero()
            result[model] += usage
        return result

    def get_total_tokens(self, since: Optional[datetime] = None) -> int:
        total = 0
        for ts, _, usage in self._history:
            if since and ts < since:
                continue
            total += usage.total_tokens
        return total


class OpenAIPlugin(BasePlugin, ILLMChat, ILLMEmbedding):
    """OpenAI 适配器插件

    提供对话补全和向量嵌入能力，内置缓存与成本统计
    """

    # 支持的模型列表
    MODELS = {
        "gpt-3.5-turbo": ModelInfo(
            model_id="gpt-3.5-turbo",
            name="GPT-3.5 Turbo",
            max_tokens=4096,
            supports_streaming=True,
            supports_tools=True,
            cost_per_1k_prompt=0.0015,
            cost_per_1k_completion=0.002,
        ),
        "gpt-4": ModelInfo(
            model_id="gpt-4",
            name="GPT-4",
            max_tokens=8192,
            supports_streaming=True,
            supports_tools=True,
            cost_per_1k_prompt=0.03,
            cost_per_1k_completion=0.06,
        ),
        "text-embedding-ada-002": ModelInfo(
            model_id="text-embedding-ada-002",
            name="Ada Embedding v2",
            max_tokens=8191,
            cost_per_1k_prompt=0.0001,
        ),
    }

    def __init__(self):
        super().__init__()
        self._client: Optional[AsyncOpenAI] = None
        self._default_model: str = "gpt-3.5-turbo"
        self._embedding_model: str = "text-embedding-ada-002"
        self._cache: LRUCache = LRUCache(capacity=100, ttl_seconds=3600)
        self._cost_tracker: CostTracker = CostTracker()
        self._cache_enabled: bool = True
        self._api_timeout: int = 60
        self._max_retries: int = 3

    @property
    def version(self) -> str:
        return "0.1.0"

    @property
    def dependencies(self) -> List[str]:
        return []

    async def install(self, context) -> None:
        await super().install(context)

        if not OPENAI_AVAILABLE:
            self.log_warn("OpenAI SDK not installed. Install with: pip install openai")
            return

        # 从配置读取参数
        api_key = self.cfg("api_key", None)
        base_url = self.cfg("base_url", None)
        organization = self.cfg("organization", None)
        self._default_model = self.cfg("default_model", "gpt-3.5-turbo")
        self._embedding_model = self.cfg("embedding_model", "text-embedding-ada-002")
        self._cache_enabled = self.cfg("cache_enabled", True)
        self._api_timeout = self.cfg("timeout", 60)
        self._max_retries = self.cfg("max_retries", 3)

        if api_key:
            self._client = AsyncOpenAI(
                api_key=api_key,
                base_url=base_url,
                organization=organization,
                timeout=self._api_timeout,
            )
            self.log_info(f"OpenAI client initialized, model: {self._default_model}")
        else:
            self.log_warn("OpenAI API key not configured, set llm.api_key in config")

    async def start(self) -> None:
        await super().start()
        self.log_info(f"OpenAI plugin started, cache size: {self._cache.size}")

    async def stop(self) -> None:
        if self._client:
            await self._client.close()
        total_cost = self._cost_tracker.get_total_cost()
        total_tokens = self._cost_tracker.get_total_tokens()
        self.log_info(f"OpenAI plugin stopped, total cost: ${total_cost:.4f}, total tokens: {total_tokens}")
        await super().stop()

    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "llm.chat": self.chat,
            "llm.completion": self.complete,  # 别名兼容
            "llm.embedding": self.embed,
            "llm.cost_tracker": self._cost_tracker,
            "llm.models": self.list_models,
        }

    # --- 公共 API ---

    def list_models(self) -> Dict[str, ModelInfo]:
        """列出所有支持的模型"""
        return dict(self.MODELS)

    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        return {
            "size": self._cache.size,
            "capacity": self._cache.capacity,
            "ttl_seconds": self._cache.ttl_seconds,
            "enabled": self._cache_enabled,
        }

    def clear_cache(self) -> None:
        """清空缓存"""
        self._cache.clear()

    def get_cost_tracker(self) -> CostTracker:
        """获取成本追踪器"""
        return self._cost_tracker

    # --- ILLMChat 实现 ---

    async def chat(
        self,
        messages: List[ChatMessage],
        max_tokens: int = 1024,
        temperature: float = 0.7,
        model: Optional[str] = None,
        use_cache: Optional[bool] = None,
        **kwargs,
    ) -> CompletionResult:
        """
        对话补全

        Args:
            messages: 对话消息列表
            max_tokens: 最大生成长度
            temperature: 采样温度 (0-1)
            model: 可选，覆盖默认模型
            use_cache: 可选，覆盖缓存开关
            **kwargs: 其他 OpenAI 参数

        Returns:
            对话结果
        """
        if not self._client:
            raise RuntimeError("OpenAI client not initialized, check API key configuration")

        target_model = model or self._default_model
        cache_key_use_cache = use_cache if use_cache is not None else self._cache_enabled

        # 检查缓存（只缓存确定性请求 temperature=0）
        if cache_key_use_cache and temperature == 0.0:
            cached = self._cache.get("chat", target_model, max_tokens, [m.to_dict() for m in messages])
            if cached:
                self.log_debug(f"Cache hit for chat request")
                return cached

        # 重试循环
        last_error = None
        for attempt in range(self._max_retries):
            try:
                response = await asyncio.wait_for(
                    self._client.chat.completions.create(
                        model=target_model,
                        messages=[m.to_dict() for m in messages],
                        max_tokens=max_tokens,
                        temperature=temperature,
                        **kwargs,
                    ),
                    timeout=self._api_timeout,
                )

                usage = CompletionUsage(
                    prompt_tokens=response.usage.prompt_tokens,
                    completion_tokens=response.usage.completion_tokens,
                    total_tokens=response.usage.total_tokens,
                )

                result = CompletionResult(
                    content=response.choices[0].message.content or "",
                    model=response.model,
                    usage=usage,
                    finish_reason=response.choices[0].finish_reason,
                    raw_response=response,
                )

                # 记录成本
                self._cost_tracker.record_usage(target_model, usage)

                # 存入缓存（只存确定性结果）
                if cache_key_use_cache and temperature == 0.0:
                    self._cache.put(result, "chat", target_model, max_tokens, [m.to_dict() for m in messages])

                return result

            except Exception as e:
                last_error = e
                if attempt < self._max_retries - 1:
                    backoff = 2 ** attempt
                    self.log_warn(f"Chat attempt {attempt + 1} failed, retry in {backoff}s: {e}")
                    await asyncio.sleep(backoff)
                else:
                    self.log_error(f"Chat failed after {self._max_retries} attempts", e)
                    raise

        raise last_error or RuntimeError("Unknown error")

    async def complete(
        self,
        prompt: str,
        max_tokens: int = 512,
        temperature: float = 0.7,
        model: Optional[str] = None,
        system_prompt: str = "You are a helpful AI assistant.",
        **kwargs,
    ) -> CompletionResult:
        """
        文本补全（使用 chat 接口模拟兼容）

        Args:
            prompt: 提示词
            max_tokens: 最大生成长度
            temperature: 采样温度
            model: 可选，覆盖默认模型
            system_prompt: 系统提示词
            **kwargs: 其他参数

        Returns:
            补全结果
        """
        messages = [
            ChatMessage(role=ChatRole.SYSTEM, content=system_prompt),
            ChatMessage(role=ChatRole.USER, content=prompt),
        ]
        return await self.chat(messages, max_tokens, temperature, model, **kwargs)

    # --- ILLMEmbedding 实现 ---

    async def embed(
        self,
        text: str,
        model: Optional[str] = None,
        **kwargs,
    ) -> EmbeddingResult:
        """
        生成文本嵌入向量

        Args:
            text: 待嵌入文本
            model: 可选，覆盖默认嵌入模型
            **kwargs: 其他 OpenAI 参数

        Returns:
            嵌入结果
        """
        if not self._client:
            raise RuntimeError("OpenAI client not initialized, check API key configuration")

        target_model = model or self._embedding_model

        for attempt in range(self._max_retries):
            try:
                response = await asyncio.wait_for(
                    self._client.embeddings.create(
                        model=target_model,
                        input=text,
                        **kwargs,
                    ),
                    timeout=self._api_timeout,
                )

                usage = CompletionUsage(
                    prompt_tokens=response.usage.prompt_tokens,
                    completion_tokens=0,
                    total_tokens=response.usage.total_tokens,
                )

                self._cost_tracker.record_usage(target_model, usage)

                return EmbeddingResult(
                    embedding=response.data[0].embedding,
                    model=response.model,
                    usage=usage,
                )

            except Exception as e:
                if attempt < self._max_retries - 1:
                    backoff = 2 ** attempt
                    self.log_warn(f"Embedding attempt {attempt + 1} failed, retry in {backoff}s: {e}")
                    await asyncio.sleep(backoff)
                else:
                    self.log_error(f"Embedding failed after {self._max_retries} attempts", e)
                    raise

        raise RuntimeError("Unknown error")

    async def embed_batch(
        self,
        texts: List[str],
        model: Optional[str] = None,
        **kwargs,
    ) -> List[EmbeddingResult]:
        """
        批量生成嵌入向量（OpenAI 支持批量，效率更高）

        Args:
            texts: 文本列表
            model: 可选，覆盖默认嵌入模型
            **kwargs: 其他 OpenAI 参数

        Returns:
            嵌入结果列表
        """
        if not self._client:
            raise RuntimeError("OpenAI client not initialized")

        target_model = model or self._embedding_model

        response = await self._client.embeddings.create(
            model=target_model,
            input=texts,
            **kwargs,
        )

        usage = CompletionUsage(
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=0,
            total_tokens=response.usage.total_tokens,
        )
        self._cost_tracker.record_usage(target_model, usage)

        # 按顺序返回（OpenAI 保证顺序）
        return [
            EmbeddingResult(
                embedding=item.embedding,
                model=response.model,
                usage=CompletionUsage.zero(),  # 总用量只记一次
            )
            for item in response.data
        ]
