"""
错误类型系统测试

测试目标：
1. PluginError 构造和属性
2. Result 类型和辅助函数
3. ErrorLevel 枚举
4. from_exception 工厂方法
"""
import pytest
from kernel.interfaces.errors import (
    ErrorLevel,
    PluginError,
    Result,
)


class TestErrorLevel:
    """错误级别枚举测试"""

    def test_error_level_has_correct_values(self):
        """枚举值正确定义"""
        assert ErrorLevel.DEBUG.value == 0
        assert ErrorLevel.WARNING.value == 1
        assert ErrorLevel.ERROR.value == 2
        assert ErrorLevel.CRITICAL.value == 3

    def test_error_level_ordering(self):
        """错误级别有严重程度顺序"""
        assert ErrorLevel.DEBUG < ErrorLevel.WARNING
        assert ErrorLevel.WARNING < ErrorLevel.ERROR
        assert ErrorLevel.ERROR < ErrorLevel.CRITICAL

    def test_error_level_is_intenum(self):
        """错误级别是 IntEnum，可以直接比较"""
        assert int(ErrorLevel.DEBUG) == 0
        assert int(ErrorLevel.CRITICAL) == 3


class TestPluginError:
    """PluginError 测试"""

    def test_error_construction_minimal(self):
        """最简化的错误构造"""
        err = PluginError(
            code="E001",
            message="Test error",
            level=ErrorLevel.ERROR,
            plugin_id="test.plugin",
            timestamp=1234567890,
        )
        assert err.code == "E001"
        assert err.message == "Test error"
        assert err.level == ErrorLevel.ERROR
        assert err.plugin_id == "test.plugin"
        assert err.timestamp == 1234567890
        assert err.retryable == False  # 默认值
        assert err.cause is None
        assert err.context is None

    def test_error_construction_full(self):
        """完整参数的错误构造"""
        err = PluginError(
            code="E002",
            message="Full error",
            level=ErrorLevel.WARNING,
            plugin_id="test.plugin",
            timestamp=1234567890,
            retryable=True,
            cause="Original stack trace",
            context={"key": "value"},
        )
        assert err.code == "E002"
        assert err.message == "Full error"
        assert err.level == ErrorLevel.WARNING
        assert err.retryable == True
        assert err.cause == "Original stack trace"
        assert err.context == {"key": "value"}

    def test_error_is_error_always_true(self):
        """is_error 方法始终返回 True"""
        err = PluginError(
            code="E001",
            message="Test",
            level=ErrorLevel.ERROR,
            plugin_id="test",
            timestamp=123,
        )
        assert err.is_error() == True

    def test_from_exception_creates_error(self):
        """from_exception 工厂方法创建错误对象"""
        try:
            raise ValueError("Something went wrong")
        except ValueError as e:
            err = PluginError.from_exception("test.plugin", e)

        assert err.code == "E-PLUGIN-EXCEPTION"
        assert err.message == "Something went wrong"
        assert err.level == ErrorLevel.ERROR
        assert err.plugin_id == "test.plugin"
        assert err.timestamp > 0  # 应该是当前时间戳
        assert err.cause is not None  # 应该包含堆栈跟踪
        assert "ValueError" in err.cause

    def test_from_exception_custom_level(self):
        """from_exception 支持自定义错误级别"""
        try:
            raise ValueError("Warning level")
        except ValueError as e:
            err = PluginError.from_exception("test.plugin", e, level=ErrorLevel.WARNING)

        assert err.level == ErrorLevel.WARNING

    def test_error_str_representation(self):
        """错误的字符串表示"""
        err = PluginError(
            code="E001",
            message="Test error",
            level=ErrorLevel.ERROR,
            plugin_id="test",
            timestamp=12345,
        )
        s = str(err)
        assert "E001" in s
        assert "Test error" in s
        assert "test" in s


class TestResultType:
    """Result 类型测试"""

    def test_result_can_be_value(self):
        """Result 可以是正常值"""
        value: Result[int] = 42
        assert value == 42
        assert not isinstance(value, PluginError)

    def test_result_can_be_error(self):
        """Result 可以是 PluginError"""
        err = PluginError(
            code="E001",
            message="Failed",
            level=ErrorLevel.ERROR,
            plugin_id="test",
            timestamp=123,
        )
        result: Result[int] = err
        assert isinstance(result, PluginError)
        assert result.code == "E001"

    def test_result_union_behavior(self):
        """Result 作为 Union 类型的行为"""
        def might_fail(should_fail: bool) -> Result[str]:
            if should_fail:
                return PluginError(
                    code="E001",
                    message="Failed",
                    level=ErrorLevel.ERROR,
                    plugin_id="test",
                    timestamp=123,
                )
            return "success"

        success = might_fail(False)
        failure = might_fail(True)

        assert success == "success"
        assert isinstance(failure, PluginError)
