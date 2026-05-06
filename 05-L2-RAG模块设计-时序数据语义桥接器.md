# Layer 2 新增：RAG/Memory 模块 - 时序数据语义桥接器

## 设计背景

### 问题陈述

物联网场景下的数据管道存在**语义断层**：

```
传感器原始数据
    ↓ (每秒/每分钟)
时序数据库 (InfluxDB/Prometheus)
    ↓ ？？？ 语义断层
大语言模型 (LLM)
```

**痛点：**
1. **数据量爆炸**：1000 个传感器 × 1 分钟采样 = 144 万条/天，直接喂给 LLM 不可能
2. **上下文浪费**：LLM 不需要知道每一秒的数值，需要的是**趋势、异常、模式**
3. **成本低效**：大量 token 浪费在机器可读的数字上，而非语义信息

### 解决方案：时序数据语义桥接层

```
原始时序数据 → [ 语义桥接器 ] → LLM 可理解的 "状态描述文档"
    [数值序列]                       [自然语言摘要]
    temp: [23,24,25,30,35]    →     "温度在过去5分钟内从23℃快速上升到35℃，
                                       上升速率 2.4℃/分钟，已触发高温告警"
```

---

## 架构定位

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 6: Agent 应用层  /  LangGraph + Skill                 │
├─────────────────────────────────────────────────────────────┤
│  Layer 5: 服务网关层                                          │
├─────────────────────────────────────────────────────────────┤
│  Layer 3: 插件运行时                                          │
├─────────────────────────────────────────────────────────────┤
│  Layer 2: 核心功能插件组                                      │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ Data IO      │  │ Logic Fence  │  │ 🔷 LLM Engine    │  │
│  │ 插件组       │  │ 插件组       │  │ 插件组            │  │
│  │              │  │              │  │                  │  │
│  │ MQTT         │  │ 规则引擎     │  │ LLM 适配器       │  │
│  │ Modbus       │  │ WASM 沙箱    │  │ 提示词管理       │  │
│  │ OPC-UA       │  │ ...          │  │ 流式输出         │  │
│  └──────────────┘  └──────────────┘  │                  │  │
│                                        │ ┌──────────────┐ │  │
│                                        │ │ 🌟 RAG/     │ │  │
│                                        │ │    Memory   │ │  │
│                                        │ │    模块     │ │  │
│                                        │ └──────────────┘ │  │
│                                        └──────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│  Layer 1: 微内核 Core                                        │
└─────────────────────────────────────────────────────────────┘
```

---

## 核心职责

### RAG/Memory 模块 = 时序数据 → 语义文档 转换器

**三大核心能力：**

| 能力 | 功能描述 | 输入 | 输出 |
|------|---------|------|------|
| **时序摘要** | 将数值序列转化为自然语言描述 | `[23,24,25,30,35]` | "5分钟内从23℃升至35℃" |
| **异常标注** | 检测异常点并生成事件描述 | 异常检测结果 | "15:30 突升20℃，超阈值3σ" |
| **模式检索** | 相似历史模式的语义化匹配 | 当前时序曲线 | "与上次故障前模式相似度87%" |

---

## 接口契约设计

### 标准接口：`ITimeseriesSemanticBridge`

```python
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class TimeSeriesPoint:
    """时序数据点"""
    timestamp: datetime
    value: float
    tags: Dict[str, str] = None


@dataclass
class SemanticDocument:
    """语义化文档（LLM 可读）"""
    doc_id: str
    timestamp: datetime
    metric_name: str
    summary: str                    # 自然语言摘要
    tags: Dict[str, str]           # 可检索标签
    embedding: Optional[List[float]] = None
    raw_data_hash: str = None      # 可溯源到原始数据


@dataclass
class RetrievalResult:
    """检索结果"""
    document: SemanticDocument
    relevance_score: float
    distance_hours: float          # 时间距离


class ITimeseriesSemanticBridge(ABC):
    """时序数据语义桥接器接口"""

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
        - 自动计算统计特征（均值、峰值、趋势、波动率）
        - 生成自然语言摘要
        - 可选：生成 embedding 向量
        """

    @abstractmethod
    async def annotate_anomaly(
        self,
        metric: str,
        anomaly_point: TimeSeriesPoint,
        severity: str,
        context_window: List[TimeSeriesPoint],
    ) -> SemanticDocument:
        """
        标注异常事件，生成异常描述文档
        - 描述异常的严重程度、持续时间、变化幅度
        - 关联上下文窗口的统计特征
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
        - 支持自然语言查询："过去一周有哪些温度异常上升的时刻？"
        - 支持按指标过滤、时间范围过滤
        """

    @abstractmethod
    async def build_context_prompt(
        self,
        metric: str,
        lookback_hours: float = 24,
    ) -> str:
        """
        构建 LLM 可用的上下文提示词
        - 聚合指定时间范围内的所有语义文档
        - 生成格式化的状态描述
        """
```

---

## 技术实现要点

### 1. 摘要生成策略（无 LLM 时也能工作）

| 策略层级 | 实现方式 | 延迟 | 成本 |
|---------|---------|------|------|
| Level 0 | 规则模板生成 | < 1ms | 0 |
| Level 1 | 本地小模型量化推理 | < 100ms | 低 |
| Level 2 | 云端大模型生成 | < 2s | 高 |

**Level 0 模板示例：**
```python
"""
{metric} 在 {duration} 分钟内:
  - 从 {start_val:.1f} 变化到 {end_val:.1f}
  - 变化速率: {rate:.2f} / 分钟
  - 峰值: {peak:.1f} 出现在 {peak_time}
  - 波动率: {volatility:.1%}
  - 状态: {trend_desc}
"""
```

### 2. 存储设计：时序 + 向量 双写

```
时序原始数据      → InfluxDB/Prometheus (保留 30 天)
      ↓
语义文档 + 向量  → SQLite + FAISS / ChromaDB (保留 1 年)
      ↓
压缩归档摘要      → 对象存储 (永久保留)
```

### 3. 典型调用流程

```
1. MQTT 插件接收传感器数据
     ↓
2. 写入时序数据库
     ↓
3. 每 5 分钟窗口触发：RAG 模块 ingest_and_summarize()
     ↓ 生成语义文档
4. 存储到向量数据库
     ↓
5. Agent 需要决策时：build_context_prompt()
     ↓
6. LLM 获得高质量、低 token 消耗的状态上下文
```

---

## 插件依赖关系

```
RAG/Memory 插件
    ↓ 依赖
LLM 适配器插件（提供 embedding 能力）
    ↓ 依赖
Data IO 插件组（提供时序数据读取能力）
```

---

## 设计原则

1. **无 LLM 也可用**：Level 0 规则模板必须能独立产出有价值的摘要
2. **渐进式增强**：可以从规则模板平滑升级到本地小模型再到云端大模型
3. **成本可控**：摘要频率、embedding 生成策略都可配置
4. **可溯源**：每个语义文档都包含原始数据的哈希，可追溯到原始时序点

---

## 下一步实现优先级

| 优先级 | 任务 | 预计工作量 |
|--------|------|-----------|
| P0 | 定义接口契约 + 内存实现 | 0.5 天 |
| P0 | Level 0 规则模板摘要生成 | 0.5 天 |
| P1 | 向量数据库集成（ChromaDB） | 1 天 |
| P1 | 上下文提示词构建器 | 0.5 天 |
| P2 | 异常标注接口 | 0.5 天 |
| P3 | 时序相似性匹配算法 | 1 天 |
