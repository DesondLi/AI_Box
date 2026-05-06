"""
内存版时序数据语义桥接器实现

Level 0 实现：基于规则模板生成摘要，无外部依赖，纯内存存储
"""

import asyncio
import hashlib
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple

from kernel.interfaces import (
    ITimeseriesSemanticBridge,
    TimeSeriesPoint,
    SemanticDocument,
    RetrievalResult,
    TrendType,
    AnomalySeverity,
)


class MemoryTimeseriesBridge(ITimeseriesSemanticBridge):
    """
    内存版时序语义桥接器

    特性：
    - Level 0 规则模板摘要生成
    - 纯内存存储，无外部依赖
    - 支持关键词检索（后续可扩展向量检索）
    """

    def __init__(self):
        self._docs: Dict[str, List[SemanticDocument]] = {}  # metric -> [doc]
        self._lock = asyncio.Lock()

    # ----- 写入路径 -----

    async def ingest_and_summarize(
        self,
        metric: str,
        points: List[TimeSeriesPoint],
        window_seconds: int = 300,
    ) -> SemanticDocument:
        if not points:
            raise ValueError("Cannot summarize empty timeseries")

        # 1. 计算统计特征
        stats = self._calculate_stats(points)

        # 2. 检测趋势
        trend = self._detect_trend(points, stats)

        # 3. 生成自然语言摘要
        summary = self._generate_summary(metric, points, stats, trend, window_seconds)

        # 4. 生成文档
        doc = SemanticDocument(
            doc_id=f"rag-{uuid.uuid4().hex[:8]}",
            timestamp=datetime.now(),
            metric_name=metric,
            summary=summary,
            tags={
                "metric": metric,
                "trend": trend.value,
                "window_seconds": str(window_seconds),
            },
            stats=stats,
            raw_data_hash=self._hash_points(points),
        )

        # 5. 存储
        async with self._lock:
            if metric not in self._docs:
                self._docs[metric] = []
            self._docs[metric].append(doc)

        return doc

    async def annotate_anomaly(
        self,
        metric: str,
        anomaly_point: TimeSeriesPoint,
        severity: AnomalySeverity,
        context_window: List[TimeSeriesPoint],
        description: str = "",
    ) -> SemanticDocument:
        # 计算上下文统计
        if context_window:
            stats = self._calculate_stats(context_window)
        else:
            stats = {"value": anomaly_point.value}

        # 异常摘要模板
        time_str = anomaly_point.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        severity_str = severity.value.upper()

        if context_window:
            base_line = stats.get("mean", 0)
            deviation = (anomaly_point.value - base_line) / base_line * 100 if base_line != 0 else 0
            summary = (
                f"[{severity_str}] {metric} 异常检测 @ {time_str}\n"
                f"  当前值: {anomaly_point.value:.2f}\n"
                f"  基线值: {base_line:.2f}\n"
                f"  偏离度: {deviation:+.1f}%\n"
            )
        else:
            summary = (
                f"[{severity_str}] {metric} 异常检测 @ {time_str}\n"
                f"  当前值: {anomaly_point.value:.2f}\n"
            )

        if description:
            summary += f"  描述: {description}\n"

        # 生成并存储文档
        doc = SemanticDocument(
            doc_id=f"anomaly-{uuid.uuid4().hex[:8]}",
            timestamp=anomaly_point.timestamp,
            metric_name=metric,
            summary=summary,
            tags={
                "metric": metric,
                "type": "anomaly",
                "severity": severity.value,
            },
            stats=stats,
        )

        async with self._lock:
            if metric not in self._docs:
                self._docs[metric] = []
            self._docs[metric].append(doc)

        return doc

    # ----- 读取路径 -----

    async def retrieve_similar(
        self,
        query: str,
        metric: Optional[str] = None,
        lookback_hours: float = 24 * 7,
        top_k: int = 5,
    ) -> List[RetrievalResult]:
        """
        简单关键词匹配（内存版实现）

        后续可升级为向量相似度匹配
        """
        cutoff_time = datetime.now() - timedelta(hours=lookback_hours)
        query_lower = query.lower()
        results = []

        async with self._lock:
            metrics = [metric] if metric else list(self._docs.keys())

            for m in metrics:
                for doc in self._docs.get(m, []):
                    # 时间过滤
                    if doc.timestamp < cutoff_time:
                        continue

                    # 简单关键词匹配分数
                    score = self._keyword_match_score(query_lower, doc.summary)
                    if score > 0:
                        distance_hours = (datetime.now() - doc.timestamp).total_seconds() / 3600
                        results.append(RetrievalResult(
                            document=doc,
                            relevance_score=score,
                            distance_hours=distance_hours,
                        ))

        # 按分数排序，取 top_k
        results.sort(key=lambda x: x.relevance_score, reverse=True)
        return results[:top_k]

    async def build_context_prompt(
        self,
        metric: str,
        lookback_hours: float = 24,
    ) -> str:
        """
        构建 LLM 可用的上下文提示词

        聚合指定时间范围内的所有语义文档，生成格式化的状态描述
        """
        cutoff_time = datetime.now() - timedelta(hours=lookback_hours)

        async with self._lock:
            docs = self._docs.get(metric, [])
            relevant_docs = [d for d in docs if d.timestamp >= cutoff_time]

        if not relevant_docs:
            return f"## {metric} 状态摘要\n\n过去 {lookback_hours} 小时内无数据\n"

        # 按时间排序
        relevant_docs.sort(key=lambda d: d.timestamp)

        # 构建提示词
        lines = [
            f"## {metric} 状态摘要（过去 {lookback_hours} 小时）",
            "",
            f"共 {len(relevant_docs)} 个数据窗口",
            "",
            "### 时间线",
            "",
        ]

        for doc in relevant_docs:
            time_str = doc.timestamp.strftime("%H:%M:%S")
            lines.append(f"[{time_str}] {doc.summary.strip()}")

        # 添加统计汇总
        if len(relevant_docs) > 1:
            lines.extend(["", "### 整体统计", ""])
            all_values = []
            for doc in relevant_docs:
                if "mean" in doc.stats:
                    all_values.append(doc.stats["mean"])

            if all_values:
                lines.extend([
                    f"- 整体均值: {sum(all_values) / len(all_values):.2f}",
                    f"- 最高值: {max(all_values):.2f}",
                    f"- 最低值: {min(all_values):.2f}",
                ])

        return "\n".join(lines)

    # ----- 管理接口 -----

    def list_metrics(self) -> List[str]:
        return list(self._docs.keys())

    def count_documents(self, metric: Optional[str] = None) -> int:
        if metric:
            return len(self._docs.get(metric, []))
        return sum(len(docs) for docs in self._docs.values())

    # ----- 内部工具方法 -----

    def _calculate_stats(self, points: List[TimeSeriesPoint]) -> Dict[str, float]:
        """计算时序统计特征"""
        values = [p.value for p in points]
        n = len(values)

        mean = sum(values) / n
        variance = sum((v - mean) ** 2 for v in values) / n
        std = variance ** 0.5

        return {
            "mean": mean,
            "min": min(values),
            "max": max(values),
            "std": std,
            "volatility": std / mean if mean != 0 else 0,
            "first": values[0],
            "last": values[-1],
            "change": values[-1] - values[0],
            "change_pct": (values[-1] - values[0]) / values[0] * 100 if values[0] != 0 else 0,
            "count": n,
        }

    def _detect_trend(self, points: List[TimeSeriesPoint], stats: Dict[str, float]) -> TrendType:
        """检测趋势类型"""
        change_pct = abs(stats["change_pct"])
        volatility = stats["volatility"]

        # 高波动率
        if volatility > 0.15:
            return TrendType.VOLATILE

        # 明显上升/下降
        if change_pct > 5:
            return TrendType.RISING if stats["change"] > 0 else TrendType.FALLING

        # 稳定
        return TrendType.STABLE

    def _generate_summary(
        self,
        metric: str,
        points: List[TimeSeriesPoint],
        stats: Dict[str, float],
        trend: TrendType,
        window_seconds: int,
    ) -> str:
        """基于规则模板生成自然语言摘要"""
        window_min = window_seconds // 60
        trend_desc = {
            TrendType.RISING: "上升趋势",
            TrendType.FALLING: "下降趋势",
            TrendType.STABLE: "保持稳定",
            TrendType.VOLATILE: "波动较大",
            TrendType.UNKNOWN: "状态未知",
        }[trend]

        duration = window_min if window_min > 0 else window_seconds
        duration_unit = "分钟" if window_min > 0 else "秒"

        # 基础模板
        summary = (
            f"{metric} 在过去 {duration} {duration_unit}内{trend_desc}。\n"
            f"  范围: {stats['min']:.1f} ~ {stats['max']:.1f}, "
            f"均值: {stats['mean']:.1f}\n"
        )

        # 有明显变化时补充说明
        if abs(stats["change_pct"]) > 1:
            direction = "上升" if stats["change"] > 0 else "下降"
            summary += (
                f"  整体{direction}了 {abs(stats['change']):.1f} "
                f"({stats['change_pct']:+.1f}%)\n"
            )

        # 高波动率提示
        if stats["volatility"] > 0.1:
            summary += f"  ⚠️ 波动率较高: {stats['volatility']:.1%}\n"

        return summary

    def _keyword_match_score(self, query: str, text: str) -> float:
        """简单关键词匹配分数"""
        query_words = set(query.split())
        text_lower = text.lower()

        matched = sum(1 for word in query_words if word in text_lower)
        if not query_words:
            return 0.0

        return matched / len(query_words)

    def _hash_points(self, points: List[TimeSeriesPoint]) -> str:
        """生成时序数据的哈希用于溯源"""
        data = "|".join(f"{p.timestamp.isoformat()}:{p.value}" for p in points)
        return hashlib.md5(data.encode()).hexdigest()[:8]
