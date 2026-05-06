"""
MQTT 输入插件示例

演示如何：
1. 继承 BasePlugin
2. 读取配置
3. 发布消息到总线
"""

import asyncio
from typing import Any

from .base_plugin import BasePlugin


class MQTTInputPlugin(BasePlugin):
    """MQTT 数据输入插件（演示版，模拟数据）"""

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def plugin_id(self) -> str:
        return "io.mqtt"

    async def start(self) -> None:
        await super().start()

        # 读取配置
        broker = self.cfg("broker", "mqtt://localhost:1883")
        topic = self.cfg("topic", "devices/#")
        interval = self.cfg("interval", 2.0)

        self.log_info(f"Starting MQTT plugin", broker=broker, topic=topic)

        # 启动后台任务模拟数据接收
        self._task = asyncio.create_task(self._simulate_data(interval))

        # 订阅 echo 服务演示 request/response
        self._message_bus.register_service("echo", self._echo_handler)
        self.log_info("Registered service: echo")

    async def stop(self) -> None:
        if hasattr(self, "_task"):
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await super().stop()
        self.log_info("MQTT plugin stopped")

    async def _simulate_data(self, interval: float) -> None:
        """模拟接收设备数据"""
        device_ids = ["sensor-001", "sensor-002", "gateway-001"]
        counter = 0

        while True:
            try:
                await asyncio.sleep(interval)
                counter += 1

                for device_id in device_ids:
                    # 发布到消息总线
                    topic = f"data/input/mqtt/{device_id}"
                    payload = {
                        "device_id": device_id,
                        "temperature": 20 + counter % 10,
                        "humidity": 50 + counter % 20,
                        "timestamp": counter,
                    }

                    await self._message_bus.publish(topic, payload, qos=0)
                    self.log_debug(f"Published data", device=device_id, topic=topic)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.log_error("Simulation task error", e)

    async def _echo_handler(self, payload: dict) -> dict:
        """简单的 echo 服务，返回收到的内容"""
        return {
            "echo": payload,
            "plugin": "io.mqtt",
        }

    def get_capabilities(self) -> dict[str, Any]:
        return {
            "data.input.mqtt": "MQTT 数据输入能力",
            "service.echo": "Echo 测试服务",
        }
