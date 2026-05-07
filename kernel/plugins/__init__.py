"""
插件基类和参考实现

新插件开发建议继承 BasePlugin，减少样板代码
"""

from .base_plugin import BasePlugin
from .mqtt_plugin import MQTTInputPlugin
from .openai_plugin import OpenAIPlugin

__all__ = [
    "BasePlugin",
    "MQTTInputPlugin",
    "OpenAIPlugin",
]
