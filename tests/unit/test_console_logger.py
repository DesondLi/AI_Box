"""
ConsoleLogger 日志系统测试

测试目标：
1. 日志格式化
2. 各级别日志方法调用
3. with_fields 子日志实例
4. ConsoleLoggerFactory 工厂
"""
import pytest
from kernel.interfaces.errors import ErrorLevel
from kernel.core.console_logger import ConsoleLogger, ConsoleLoggerFactory


class TestConsoleLogger:
    """ConsoleLogger 测试"""

    def test_logger_creation_with_plugin_id(self):
        """创建日志实例时保存 plugin_id"""
        logger = ConsoleLogger("test.plugin")
        assert logger._plugin_id == "test.plugin"

    def test_logger_creation_with_fields(self):
        """创建日志实例时可以带初始字段"""
        logger = ConsoleLogger("test.plugin", {"env": "test", "version": "1.0"})
        assert logger._fields == {"env": "test", "version": "1.0"}

    def test_logger_creation_without_fields(self):
        """创建日志实例时不带初始字段默认是空 dict"""
        logger = ConsoleLogger("test.plugin")
        assert logger._fields == {}

    def test_format_includes_timestamp(self):
        """格式化输出包含时间戳"""
        logger = ConsoleLogger("test.plugin")
        output = logger._format(ErrorLevel.DEBUG, "Test message")
        # 时间戳格式应该类似 HH:MM:SS
        assert len(output.split()[0]) == 8  # HH:MM:SS has 8 chars

    def test_format_includes_level_name(self):
        """格式化输出包含级别名称"""
        logger = ConsoleLogger("test.plugin")

        output = logger._format(ErrorLevel.DEBUG, "Test")
        assert "DEBUG" in output

        output = logger._format(ErrorLevel.WARNING, "Test")
        assert "WARN" in output

        output = logger._format(ErrorLevel.ERROR, "Test")
        assert "ERROR" in output

        output = logger._format(ErrorLevel.CRITICAL, "Test")
        assert "CRIT" in output

    def test_format_includes_plugin_id(self):
        """格式化输出包含插件 ID"""
        logger = ConsoleLogger("my.plugin")
        output = logger._format(ErrorLevel.DEBUG, "Test message")
        assert "my.plugin" in output

    def test_format_includes_message(self):
        """格式化输出包含消息内容"""
        logger = ConsoleLogger("test.plugin")
        output = logger._format(ErrorLevel.DEBUG, "Hello World")
        assert "Hello World" in output

    def test_format_includes_extra_fields(self):
        """格式化输出包含额外字段"""
        logger = ConsoleLogger("test.plugin")
        output = logger._format(ErrorLevel.DEBUG, "Test", user="alice", action="login")
        assert "user=alice" in output
        assert "action=login" in output

    def test_format_merges_initial_and_extra_fields(self):
        """初始字段和额外字段合并"""
        logger = ConsoleLogger("test.plugin", {"env": "prod"})
        output = logger._format(ErrorLevel.DEBUG, "Test", request_id="123")
        assert "env=prod" in output
        assert "request_id=123" in output

    def test_debug_method(self, capsys):
        """debug 方法输出正确"""
        logger = ConsoleLogger("test.plugin")
        logger.debug("Debug message")
        captured = capsys.readouterr()
        assert "DEBUG" in captured.out
        assert "Debug message" in captured.out

    def test_info_method(self, capsys):
        """info 方法输出正确（用 WARNING 颜色）"""
        logger = ConsoleLogger("test.plugin")
        logger.info("Info message")
        captured = capsys.readouterr()
        # info 用 WARNING 颜色，所以级别名称应该是 WARN
        assert "WARN" in captured.out
        assert "Info message" in captured.out

    def test_warn_method(self, capsys):
        """warn 方法输出正确"""
        logger = ConsoleLogger("test.plugin")
        logger.warn("Warning message")
        captured = capsys.readouterr()
        assert "WARN" in captured.out
        assert "Warning message" in captured.out

    def test_error_method(self, capsys):
        """error 方法输出正确"""
        logger = ConsoleLogger("test.plugin")
        logger.error("Error message")
        captured = capsys.readouterr()
        assert "ERROR" in captured.out
        assert "Error message" in captured.out

    def test_error_method_with_exception(self, capsys):
        """error 方法带异常信息"""
        logger = ConsoleLogger("test.plugin")
        exc = ValueError("Something bad")
        logger.error("Error occurred", exception=exc)
        captured = capsys.readouterr()
        assert "ERROR" in captured.out
        assert "Error occurred" in captured.out
        assert "Something bad" in captured.out

    def test_with_fields_creates_new_instance(self):
        """with_fields 创建新的日志实例"""
        logger = ConsoleLogger("test.plugin", {"env": "test"})
        child = logger.with_fields(request_id="123")

        # 是新实例
        assert child is not logger
        # 同样的 plugin_id
        assert child._plugin_id == "test.plugin"
        # 继承父级字段
        assert child._fields["env"] == "test"
        # 有新字段
        assert child._fields["request_id"] == "123"
        # 父级不变
        assert "request_id" not in logger._fields

    def test_child_logger_inherits_plugin_id(self):
        """子日志器继承父级 plugin_id"""
        logger = ConsoleLogger("parent.plugin")
        child = logger.with_fields(child="true")
        assert child._plugin_id == "parent.plugin"


class TestConsoleLoggerFactory:
    """ConsoleLoggerFactory 测试"""

    def test_factory_creates_logger_for_plugin(self):
        """工厂创建对应插件的日志实例"""
        factory = ConsoleLoggerFactory()
        logger = factory.for_plugin("factory.test")
        assert isinstance(logger, ConsoleLogger)
        assert logger._plugin_id == "factory.test"

    def test_factory_creates_new_instance_each_time(self):
        """每次调用创建新实例"""
        factory = ConsoleLoggerFactory()
        logger1 = factory.for_plugin("plugin.a")
        logger2 = factory.for_plugin("plugin.b")

        assert logger1 is not logger2
        assert logger1._plugin_id == "plugin.a"
        assert logger2._plugin_id == "plugin.b"
