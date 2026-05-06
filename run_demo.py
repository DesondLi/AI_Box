#!/usr/bin/env python3
"""
微内核演示启动脚本（在项目根目录运行）
"""

import asyncio
import sys
from pathlib import Path

# 确保 kernel 包在 path 中
sys.path.insert(0, str(Path(__file__).parent))

from kernel.core import MicroKernel
from kernel.plugins import MQTTInputPlugin


async def message_monitor(topic: str, payload: dict) -> None:
    """消息监控器：打印所有收到的消息"""
    print(f"\n📨 [{topic}]")
    for k, v in payload.items():
        print(f"   {k}: {v}")


async def main():
    print("=" * 60)
    print("  微内核演示系统")
    print("=" * 60)

    # 1. 创建内核
    kernel = MicroKernel()

    # 2. 加载配置
    kernel.config.bulk_load({
        "io.mqtt.broker": "mqtt://localhost:1883",
        "io.mqtt.topic": "devices/#",
        "io.mqtt.interval": 1.5,
    })

    # 3. 注册插件
    mqtt_plugin = MQTTInputPlugin()
    kernel.register_plugin(mqtt_plugin)

    # 4. 订阅所有消息
    await kernel.message_bus.subscribe("data/input/#", message_monitor)

    # 5. 启动内核
    try:
        await kernel.start()

        # 6. 演示服务调用
        print("\n" + "=" * 60)
        print("  测试服务调用：echo")
        print("=" * 60)

        result = await kernel.message_bus.request(
            "echo",
            {"hello": "world", "test": 123}
        )
        print(f"[OK] 服务调用结果: {result}")

        # 7. 查看已注册的能力
        print("\n" + "=" * 60)
        print("  已注册能力")
        print("=" * 60)

        for cap, desc in mqtt_plugin.get_capabilities().items():
            print(f"  - {cap}: {desc}")

        # 8. 运行 5 秒
        print("\n" + "=" * 60)
        print("  运行 5 秒，观察数据流动...")
        print("=" * 60)
        await asyncio.sleep(5)

    except KeyboardInterrupt:
        print("\n\n收到停止信号...")
    except Exception as e:
        print(f"启动失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await kernel.stop()
        print("\n" + "=" * 60)
        print("  演示结束")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
