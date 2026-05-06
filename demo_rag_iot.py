#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RAG/Memory 模块演示：IoT 温度监控场景

展示完整流程：
1. 时序数据摄入 → 语义摘要
2. 异常检测 → 异常标注
3. 构建 LLM 上下文
"""

import asyncio
from datetime import datetime, timedelta

from kernel.core.memory_rag_bridge import MemoryTimeseriesBridge
from kernel.interfaces import TimeSeriesPoint, AnomalySeverity


def generate_sensor_data(
    start_temp: float,
    end_temp: float,
    n_points: int = 60,
    sensor_id: str = "sensor-001",
) -> list:
    """生成模拟传感器数据（1 分钟窗口，1 秒采样）"""
    now = datetime.now()
    step = (end_temp - start_temp) / n_points
    return [
        TimeSeriesPoint(
            timestamp=now - timedelta(seconds=(n_points - i)),
            value=start_temp + step * i,
            tags={"sensor": sensor_id, "location": "reactor-A"},
        )
        for i in range(n_points)
    ]


async def demo_iot_monitoring():
    print("=" * 70)
    print("  RAG/Memory 模块演示：IoT 反应堆温度监控")
    print("=" * 70)

    bridge = MemoryTimeseriesBridge()
    metric = "reactor_A_temperature"

    # ----------------------------------------------------------------
    # Phase 1: 正常运行阶段
    # ----------------------------------------------------------------
    print("\n" + "=" * 70)
    print("  [Phase 1] 正常运行 - 温度稳定在 80~85℃")
    print("=" * 70)

    normal_data = generate_sensor_data(80.0, 85.0)
    doc_normal = await bridge.ingest_and_summarize(metric, normal_data, 60)
    print(f"\n[OK] 生成语义文档: {doc_normal.doc_id}")
    print(f"\n摘要内容:\n{doc_normal.summary}")

    # ----------------------------------------------------------------
    # Phase 2: 温度缓慢上升
    # ----------------------------------------------------------------
    print("\n" + "=" * 70)
    print("  [Phase 2] 温度上升 - 从 85℃ 升至 100℃")
    print("=" * 70)

    rising_data = generate_sensor_data(85.0, 100.0)
    doc_rising = await bridge.ingest_and_summarize(metric, rising_data, 60)
    print(f"\n[OK] 生成语义文档: {doc_rising.doc_id}")
    print(f"\n摘要内容:\n{doc_rising.summary}")

    # ----------------------------------------------------------------
    # Phase 3: 异常检测 - 温度飙升至 150℃
    # ----------------------------------------------------------------
    print("\n" + "=" * 70)
    print("  [Phase 3] 异常检测 - 温度突升至 150℃ ")
    print("=" * 70)

    anomaly_point = TimeSeriesPoint(
        timestamp=datetime.now(),
        value=150.0,
        tags={"sensor": "sensor-001", "alert": "true"},
    )

    doc_anomaly = await bridge.annotate_anomaly(
        metric=metric,
        anomaly_point=anomaly_point,
        severity=AnomalySeverity.CRITICAL,
        context_window=rising_data,
        description="冷却系统故障，温度异常飙升，已触发紧急停机",
    )

    print(f"\n[OK] 生成异常文档: {doc_anomaly.doc_id}")
    print(f"\n异常摘要:\n{doc_anomaly.summary}")

    # ----------------------------------------------------------------
    # Phase 4: 构建 LLM 上下文
    # ----------------------------------------------------------------
    print("\n" + "=" * 70)
    print("  [Phase 4] 构建 LLM 上下文提示词")
    print("=" * 70)

    context = await bridge.build_context_prompt(metric, lookback_hours=1)
    print("\n" + "-" * 70)
    print(context)
    print("-" * 70)

    # ----------------------------------------------------------------
    # Phase 5: 检索相似历史模式
    # ----------------------------------------------------------------
    print("\n" + "=" * 70)
    print("  [Phase 5] 检索相似历史模式")
    print("=" * 70)

    results = await bridge.retrieve_similar(
        query="温度异常 飙升 CRITICAL",
        metric=metric,
        top_k=3,
    )

    print(f"\n找到 {len(results)} 个相关文档:")
    for i, result in enumerate(results, 1):
        print(f"\n  [{i}] 相关性: {result.relevance_score:.0%}")
        print(f"      {result.document.summary[:80]}...")

    # ----------------------------------------------------------------
    # Stats
    # ----------------------------------------------------------------
    print("\n" + "=" * 70)
    print("  演示完成")
    print("=" * 70)
    print(f"\n📊 统计:")
    print(f"   - 文档总数: {bridge.count_documents()}")
    print(f"   - 指标数量: {len(bridge.list_metrics())}")
    print(f"\n💡 Token 对比:")
    print(f"   - 原始数据: 3 × 60 个浮点数 ≈ 1800 tokens")
    print(f"   - 语义化后: 3 个摘要 ≈ 200 tokens")
    print(f"   - 压缩率: 9:1  🚀")


if __name__ == "__main__":
    asyncio.run(demo_iot_monitoring())
