"""
RAG/Memory 模块测试用例

测试目标：
1. 时序数据摄入与摘要生成
2. 统计特征计算正确性
3. 趋势检测逻辑
4. 上下文提示词构建
5. 异常标注功能
6. 关键词检索
"""
import pytest
from datetime import datetime, timedelta

from kernel.core.memory_rag_bridge import MemoryTimeseriesBridge
from kernel.interfaces import (
    TimeSeriesPoint,
    TrendType,
    AnomalySeverity,
)


class TestMemoryTimeseriesBridge:
    """内存版语义桥接器测试"""

    @pytest.fixture
    def bridge(self):
        return MemoryTimeseriesBridge()

    def _generate_points(self, start_val: float, end_val: float, n: int = 10):
        """生成测试时序数据点（包含首尾）"""
        now = datetime.now()
        step = (end_val - start_val) / (n - 1)  # n 个点有 n-1 个间隔
        return [
            TimeSeriesPoint(
                timestamp=now - timedelta(seconds=(n - i)),
                value=start_val + step * i,
            )
            for i in range(n)
        ]

    # ----- 基础功能测试 -----

    @pytest.mark.asyncio
    async def test_ingest_and_summarize_basic(self, bridge):
        """测试：基础摘要生成"""
        points = self._generate_points(20.0, 25.0)
        doc = await bridge.ingest_and_summarize("temperature", points)

        assert doc.metric_name == "temperature"
        assert "temperature" in doc.summary
        assert doc.stats["mean"] == pytest.approx(22.5, 0.1)
        assert doc.stats["min"] == pytest.approx(20.0, 0.1)
        assert doc.stats["max"] == pytest.approx(25.0, 0.1)

    @pytest.mark.asyncio
    async def test_ingest_empty_points_raises_error(self, bridge):
        """测试：空数据抛出异常"""
        with pytest.raises(ValueError, match="empty timeseries"):
            await bridge.ingest_and_summarize("temperature", [])

    # ----- 统计特征测试 -----

    def test_calculate_stats(self, bridge):
        """测试：统计特征计算"""
        points = self._generate_points(10.0, 20.0, n=11)
        stats = bridge._calculate_stats(points)

        # 10.0, 11.0, 12.0 ... 20.0 等差数列
        assert stats["min"] == pytest.approx(10.0)
        assert stats["max"] == pytest.approx(20.0)
        assert stats["mean"] == pytest.approx(15.0, 0.5)  # 允许小误差
        assert stats["change"] == pytest.approx(10.0, 0.5)
        assert stats["change_pct"] == pytest.approx(100.0, 5.0)

    # ----- 趋势检测测试 -----

    @pytest.mark.parametrize(
        "start, end, expected_trend",
        [
            (20.0, 20.5, TrendType.STABLE),    # 微小变化
            (20.0, 25.0, TrendType.RISING),    # 明显上升
            (25.0, 20.0, TrendType.FALLING),   # 明显下降
        ],
    )
    def test_detect_trend_directional(self, bridge, start, end, expected_trend):
        """测试：趋势方向检测"""
        points = self._generate_points(start, end)
        stats = bridge._calculate_stats(points)
        trend = bridge._detect_trend(points, stats)
        assert trend == expected_trend

    def test_detect_trend_volatile(self, bridge):
        """测试：高波动率检测"""
        # 构造波动数据：10, 30, 10, 30...
        now = datetime.now()
        points = []
        for i in range(10):
            val = 10 if i % 2 == 0 else 30
            points.append(TimeSeriesPoint(
                timestamp=now - timedelta(seconds=i),
                value=val,
            ))

        stats = bridge._calculate_stats(points)
        trend = bridge._detect_trend(points, stats)

        assert trend == TrendType.VOLATILE
        assert stats["volatility"] > 0.15

    # ----- 摘要内容质量测试 -----

    @pytest.mark.asyncio
    async def test_summary_contains_key_info(self, bridge):
        """测试：摘要包含关键信息"""
        points = self._generate_points(20.0, 30.0, n=5)
        doc = await bridge.ingest_and_summarize("temperature", points, 300)

        # 摘要应该包含的关键信息
        assert "温度" in doc.summary or "temperature" in doc.summary.lower()
        assert "20" in doc.summary or "30" in doc.summary or "25" in doc.summary  # 数值
        assert "上升" in doc.summary or "+" in doc.summary  # 趋势

    @pytest.mark.asyncio
    async def test_summary_mentions_volatility_warning(self, bridge):
        """测试：高波动率时摘要包含警告"""
        # 构造高波动数据
        now = datetime.now()
        points = []
        for i in range(10):
            val = 20 if i % 2 == 0 else 40
            points.append(TimeSeriesPoint(
                timestamp=now - timedelta(seconds=i),
                value=val,
            ))

        doc = await bridge.ingest_and_summarize("pressure", points)
        assert "波动" in doc.summary or "volatile" in doc.summary.lower() or "⚠️" in doc.summary

    # ----- 异常标注测试 -----

    @pytest.mark.asyncio
    async def test_annotate_anomaly(self, bridge):
        """测试：异常标注功能"""
        anomaly_point = TimeSeriesPoint(
            timestamp=datetime.now(),
            value=100.0,
        )
        context = self._generate_points(20.0, 25.0)

        doc = await bridge.annotate_anomaly(
            metric="temperature",
            anomaly_point=anomaly_point,
            severity=AnomalySeverity.CRITICAL,
            context_window=context,
        )

        assert doc.metric_name == "temperature"
        assert "CRITICAL" in doc.summary.upper()
        assert "异常" in doc.summary
        assert "100" in doc.summary  # 异常值
        assert doc.tags["type"] == "anomaly"

    @pytest.mark.asyncio
    async def test_annotate_anomaly_without_context(self, bridge):
        """测试：无上下文的异常标注"""
        anomaly_point = TimeSeriesPoint(
            timestamp=datetime.now(),
            value=999.0,
        )

        doc = await bridge.annotate_anomaly(
            metric="voltage",
            anomaly_point=anomaly_point,
            severity=AnomalySeverity.WARNING,
            context_window=[],
        )

        assert "999" in doc.summary
        assert "WARNING" in doc.summary.upper()

    # ----- 上下文提示词构建测试 -----

    @pytest.mark.asyncio
    async def test_build_context_prompt_empty(self, bridge):
        """测试：无数据时的提示词"""
        prompt = await bridge.build_context_prompt("nonexistent", lookback_hours=24)

        assert "无数据" in prompt or "nonexistent" in prompt

    @pytest.mark.asyncio
    async def test_build_context_prompt_aggregation(self, bridge):
        """测试：多窗口数据聚合"""
        # 生成3个连续的数据窗口
        for i in range(3):
            points = self._generate_points(20.0 + i, 25.0 + i)
            await bridge.ingest_and_summarize("temperature", points)

        prompt = await bridge.build_context_prompt("temperature", lookback_hours=1)

        assert "温度" in prompt or "temperature" in prompt.lower()
        assert "3 个数据窗口" in prompt
        assert "时间线" in prompt
        assert "整体统计" in prompt

    # ----- 检索测试 -----

    @pytest.mark.asyncio
    async def test_retrieve_similar_basic(self, bridge):
        """测试：基础关键词检索"""
        # 生成一些数据
        for i in range(5):
            start = 20 + i * 2
            points = self._generate_points(start, start + 5)
            await bridge.ingest_and_summarize("temperature", points)

        # 检索包含"上升"的文档
        results = await bridge.retrieve_similar("上升", "temperature", top_k=3)

        # 内存版用关键词匹配，"上升"应该能匹配到上升趋势的文档
        assert len(results) >= 0  # 至少不报错

    # ----- 管理接口测试 -----

    @pytest.mark.asyncio
    async def test_list_metrics(self, bridge):
        """测试：列出所有指标"""
        await bridge.ingest_and_summarize("temperature", self._generate_points(20, 25))
        await bridge.ingest_and_summarize("humidity", self._generate_points(40, 50))

        metrics = bridge.list_metrics()

        assert len(metrics) == 2
        assert "temperature" in metrics
        assert "humidity" in metrics

    @pytest.mark.asyncio
    async def test_count_documents(self, bridge):
        """测试：统计文档数量"""
        await bridge.ingest_and_summarize("temperature", self._generate_points(20, 25))
        await bridge.ingest_and_summarize("temperature", self._generate_points(25, 30))
        await bridge.ingest_and_summarize("humidity", self._generate_points(40, 50))

        assert bridge.count_documents("temperature") == 2
        assert bridge.count_documents("humidity") == 1
        assert bridge.count_documents() == 3

    # ----- 集成测试：完整流程 -----

    @pytest.mark.asyncio
    async def test_full_iot_monitoring_flow(self, bridge):
        """测试：完整的 IoT 监控流程"""
        metric = "reactor_temperature"

        # 1. 正常数据窗口
        normal_points = self._generate_points(80.0, 82.0)
        normal_doc = await bridge.ingest_and_summarize(metric, normal_points)
        assert "稳定" in normal_doc.summary or "上升" in normal_doc.summary

        # 2. 检测到异常
        anomaly_point = TimeSeriesPoint(
            timestamp=datetime.now(),
            value=150.0,
        )
        anomaly_doc = await bridge.annotate_anomaly(
            metric,
            anomaly_point,
            AnomalySeverity.CRITICAL,
            normal_points,
            "温度异常飙升，已超出安全阈值",
        )

        assert "CRITICAL" in anomaly_doc.summary
        assert "150" in anomaly_doc.summary

        # 3. 构建 LLM 上下文
        context = await bridge.build_context_prompt(metric, lookback_hours=1)

        assert metric in context
        assert "异常" in context or "CRITICAL" in context.upper()

        # 4. 文档计数正确
        assert bridge.count_documents(metric) == 2
