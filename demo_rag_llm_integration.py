#!/usr/bin/env python3
"""
RAG + LLM 引擎集成演示

完整链路：
1. 生成模拟时序数据（温度传感器）
2. RAG 语义桥接器生成摘要
3. LLM 引擎基于摘要做智能决策

运行前需要：
1. pip install openai
2. 设置 OPENAI_API_KEY 环境变量或在代码中配置
"""

import asyncio
import os
from datetime import datetime, timedelta
from typing import List

# 设置 UTF-8 输出（Windows 控制台）
if os.name == 'nt':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')

from kernel.core.kernel import MicroKernel
from kernel.core.memory_rag_bridge import MemoryTimeseriesSemanticBridge
from kernel.plugins.openai_plugin import OpenAIPlugin
from kernel.interfaces import (
    TimeSeriesPoint,
    ChatMessage,
    ChatRole,
)


async def demo_sensor_monitoring():
    """
    场景：智能温度监控报警

    模拟一个机房温度传感器，每 5 分钟采样一次。
    RAG 桥接器将时序数据转为自然语言摘要。
    LLM 基于摘要判断是否需要报警，并给出建议。
    """
    print("=" * 60)
    print("🤖 AI 盒子 - RAG + LLM 智能监控演示")
    print("=" * 60)
    print()

    # --- 初始化内核 ---
    print("[1/5] 初始化微内核...")
    kernel = MicroKernel()

    # 配置 OpenAI API Key
    api_key = os.getenv("OPENAI_API_KEY", "")
    if api_key:
        kernel.config.set("llm.api_key", api_key)
        kernel.config.set("llm.default_model", "gpt-3.5-turbo")
        print(f"       ✓ OpenAI API Key 已配置")
    else:
        print("       ⚠ 未配置 OPENAI_API_KEY，将使用 Mock 模式")

    # 注册插件
    rag_bridge = MemoryTimeseriesSemanticBridge()
    llm_plugin = OpenAIPlugin()

    await kernel.install_plugin(rag_bridge)
    await kernel.install_plugin(llm_plugin)
    await kernel.start()
    print("       ✓ 内核启动完成")
    print()

    # --- 生成模拟时序数据 ---
    print("[2/5] 生成模拟时序数据...")
    now = datetime.now()
    points: List[TimeSeriesPoint] = []

    # 生成 24 小时的温度数据（每 15 分钟一个采样点）
    for i in range(96):
        ts = now - timedelta(minutes=15 * (96 - i))

        # 模拟温度波动：
        # - 白天高，夜晚低
        # - 第 60-70 个点模拟一个温度飙升（空调故障）
        hour = ts.hour
        base_temp = 22 + 4 * ((hour - 8) % 24) / 12 if 8 <= hour <= 20 else 20

        if 60 <= i <= 70:
            base_temp += 8 + (i - 65) * 0.5  # 温度飙升

        # 加一点噪声
        temperature = base_temp + (i % 3 - 1) * 0.3

        points.append(TimeSeriesPoint(
            timestamp=ts,
            value=round(temperature, 2),
            tags={"room": "A1", "sensor": "temp-001"},
        ))

    print(f"       ✓ 生成 {len(points)} 个温度采样点")
    print(f"       时间范围：{points[0].timestamp.strftime('%H:%M')} → {points[-1].timestamp.strftime('%H:%M')}")
    print(f"       温度范围：{min(p.value for p in points):.1f}°C → {max(p.value for p in points):.1f}°C")
    print()

    # --- RAG 语义摘要 ---
    print("[3/5] RAG 语义桥接器处理...")

    # 按 2 小时窗口分块处理
    window_size = 8  # 每窗口 8 个点 = 2 小时
    all_docs = []

    for i in range(0, len(points), window_size):
        window = points[i:i + window_size]
        doc = await rag_bridge.ingest_and_summarize(
            metric="room.temperature",
            points=window,
            window_seconds=7200,  # 2 小时
        )
        all_docs.append(doc)
        print(f"       窗口 {i//window_size + 1}: {doc.summary}")

    print(f"       ✓ 生成 {len(all_docs)} 个语义文档")
    print()

    # --- 构建 LLM 上下文 ---
    print("[4/5] 构建 LLM 上下文...")

    # 聚合 24 小时数据
    context_prompt = await rag_bridge.build_context_prompt(
        metric="room.temperature",
        lookback_hours=24,
    )

    print(f"       上下文长度：{len(context_prompt)} 字符")
    print()

    # --- LLM 智能分析 ---
    print("[5/5] LLM 智能分析...")
    print()

    system_prompt = """
你是一个专业的机房监控分析师。请基于提供的温度监控数据，分析并给出建议。

请按以下格式输出：
【状态评估】正常/异常/警告
【关键发现】（3-5 条要点）
【建议措施】（具体可执行的建议）
【风险评分】0-10（10 为最严重）
"""

    user_prompt = f"""
以下是机房 A1 区域最近 24 小时的温度监控摘要：

{context_prompt}

请分析当前机房温度状态，判断是否存在异常，并给出专业建议。
"""

    print("-" * 60)
    print("📊 LLM 分析结果：")
    print("-" * 60)
    print()

    if api_key:
        # 真实 LLM 调用
        messages = [
            ChatMessage(role=ChatRole.SYSTEM, content=system_prompt),
            ChatMessage(role=ChatRole.USER, content=user_prompt),
        ]

        result = await llm_plugin.chat(
            messages=messages,
            max_tokens=800,
            temperature=0.3,  # 低温度，稳定输出
        )

        print(result.content)
        print()
        print(f"Token 用量：{result.usage.prompt_tokens} + {result.usage.completion_tokens} = {result.usage.total_tokens}")

        # 成本统计
        cost_tracker = llm_plugin.get_cost_tracker()
        total_cost = cost_tracker.get_total_cost()
        print(f"累计成本：${total_cost:.4f}")
    else:
        # Mock 模式输出
        print("⚠  使用 Mock 输出（未配置 OpenAI API Key）")
        print()
        print("【状态评估】警告")
        print()
        print("【关键发现】")
        print("- 18:00-21:00 期间温度异常升高至 30°C 以上")
        print("- 超出正常运行范围（建议 ≤ 26°C）")
        print("- 持续时间约 3 小时，可能影响设备寿命")
        print("- 当前温度已回落至正常范围，但存在复发风险")
        print()
        print("【建议措施】")
        print("1. 检查空调系统运行状态，确认是否需要维护")
        print("2. 增加该区域的温度采样频率至 1 分钟")
        print("3. 设置 28°C 阈值告警，提前干预")
        print("4. 考虑检查机柜散热情况，是否存在局部热点")
        print("5. 回顾历史同期数据，判断是否为季节性波动")
        print()
        print("【风险评分】7/10")
        print()
        print("Token 用量：0")
        print("累计成本：$0.0000")

    print()
    print("-" * 60)

    # --- 语义检索演示 ---
    print()
    print("🔍 语义检索演示：")
    print()
    query = "温度异常升高的时刻"
    print(f"查询：\"{query}\"")
    print()

    results = await rag_bridge.retrieve_similar(query, metric="room.temperature", top_k=3)

    print(f"找到 {len(results)} 个相关结果：")
    for i, r in enumerate(results, 1):
        print(f"  {i}. 相关性 {r.relevance_score:.2f} | {r.document.summary}")

    print()
    print("=" * 60)
    print("✅ 演示完成！")
    print()
    print("下一步建议：")
    print("- 连接真实 MQTT broker 接收真实传感器数据")
    print("- 添加规则引擎实现阈值自动告警")
    print("- 集成向量数据库支持长期记忆检索")
    print()

    # 清理
    await kernel.stop()


async def demo_simple_chat():
    """
    简单对话演示
    """
    print("=" * 60)
    print("💬 简单对话演示")
    print("=" * 60)
    print()

    kernel = MicroKernel()

    api_key = os.getenv("OPENAI_API_KEY", "")
    if api_key:
        kernel.config.set("llm.api_key", api_key)
    else:
        print("⚠ 未配置 OPENAI_API_KEY，跳过真实调用")
        return

    llm_plugin = OpenAIPlugin()
    await kernel.install_plugin(llm_plugin)
    await kernel.start()

    messages = [
        ChatMessage(role=ChatRole.SYSTEM, content="你是一个 IoT 专家，回答简洁专业。"),
        ChatMessage(role=ChatRole.USER, content="IoT 网关中，时序数据如何高效地传给 LLM？"),
    ]

    print("提问：IoT 网关中，时序数据如何高效地传给 LLM？")
    print()

    result = await llm_plugin.chat(
        messages=messages,
        max_tokens=300,
        temperature=0.5,
    )

    print("回答：")
    print(result.content)
    print()
    print(f"Token: {result.usage.total_tokens}")

    await kernel.stop()


if __name__ == "__main__":
    print()

    # 运行主要演示
    asyncio.run(demo_sensor_monitoring())

    # 可选：运行简单对话演示
    # asyncio.run(demo_simple_chat())
