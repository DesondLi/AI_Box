"""
RAG/Memory 模块接口定义

时序数据语义桥接器：将机器可读的数值序列，转化为 LLM 可读的自然语言描述
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import List, Dict, Optional


class TrendType(Enum):
    """时序趋势类型"""
    RISING = "rising"           # 上升
    FALLING = "falling"         # 下降
    STABLE = "stable"           # 稳定
    VOLATILE = "volatile"       # 波动
    UNKNOWN = "unknown"         # 未知


class AnomalySeverity(Enum):
    """异常严重程度"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class TimeSeriesPoint:
    """时序数据点"""
    timestamp: datetime
    value: float
    tags: Dict[str, str] = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = {}


@dataclass
class SemanticDocument:
    """语义化文档（LLM 可读）

    这是时序数据与 LLM 之间的标准交换格式
    """
    doc_id: str
    timestamp: datetime
    metric_name: str
    summary: str                    # 自然语言摘要（核心字段）
    tags: Dict[str, str]           # 可检索标签
    stats: Dict[str, float] = None  # 统计特征（均值、峰值、波动率等）
    embedding: Optional[List[float]] = None
    raw_data_hash: str = None      # 可溯源到原始数据

    def __post_init__(self):
        if self.stats is None:
            self.stats = {}
        if self.tags is None:
            self.tags = {}


@dataclass
class RetrievalResult:
    """检索结果"""
    document: SemanticDocument
    relevance_score: float
    distance_hours: float          # 时间距离（小时）


class ITimeseriesSemanticBridge(ABC):
    """时序数据语义桥接器接口

    Layer 2 - LLM Engine 插件组的核心模块
    """

    # ----- 写入路径 -----

    @abstractmethod
    async def ingest_and_summarize(
        self,
        metric: str,
        points: List[TimeSeriesPoint],
        window_seconds: int = 300,
    ) -> SemanticDocument:
        """
        摄入时序数据窗口，生成语义文档

        流程：
        1. 计算统计特征（均值、峰值、趋势、波动率）
        2. 基于规则/模型生成自然语言摘要
        3. 存储语义文档（可选生成 embedding）

        Args:
            metric: 指标名称，如 "temperature"
            points: 时序数据点列表
            window_seconds: 窗口时长（秒）

        Returns:
            生成的语义文档
        """

    @abstractmethod
    async def annotate_anomaly(
        self,
        metric: str,
        anomaly_point: TimeSeriesPoint,
        severity: AnomalySeverity,
        context_window: List[TimeSeriesPoint],
        description: str = "",
    ) -> SemanticDocument:
        """
        标注异常事件，生成异常描述文档

        Args:
            metric: 指标名称
            anomaly_point: 异常数据点
            severity: 严重程度
            context_window: 异常前后的上下文数据点
            description: 人工补充描述

        Returns:
            异常描述文档
        """

    # ----- 读取路径 -----

    @abstractmethod
    async def retrieve_similar(
        self,
        query: str,
        metric: Optional[str] = None,
        lookback_hours: float = 24 * 7,
        top_k: int = 5,
    ) -> List[RetrievalResult]:
        """
        语义检索相似历史状态

        支持自然语言查询：
        - "过去一周有哪些温度异常上升的时刻？"
        - "查找与当前模式相似的历史数据"

        Args:
            query: 自然语言查询
            metric: 可选，按指标过滤
            lookback_hours: 回溯时间范围（小时）
            top_k: 返回结果数量

        Returns:
            按相关性排序的检索结果列表
        """

    @abstractmethod
    async def build_context_prompt(
        self,
        metric: str,
        lookback_hours: float = 24,
    ) -> str:
        """
        构建 LLM 可用的上下文提示词

        聚合指定时间范围内的所有语义文档，生成格式化的状态描述。

        Args:
            metric: 指标名称
            lookback_hours: 回溯时长（小时）

        Returns:
            可直接插入 LLM 提示词的格式化字符串
        """

    # ----- 管理接口 -----

    @abstractmethod
    def list_metrics(self) -> List[str]:
        """列出所有已存储的指标名称"""

    @abstractmethod
    def count_documents(self, metric: Optional[str] = None) -> int:
        """统计文档数量"""
