#!/usr/bin/env python3
"""
配置持久化与热重载演示

演示内容：
1. 配置写入磁盘（JSON/YAML）
2. 从磁盘加载配置
3. 外部修改配置文件，内核自动热重载
4. 命名空间隔离
5. watcher 监听变更
"""

import asyncio
import os
import time
import json
from pathlib import Path

# 设置 UTF-8 输出
if os.name == 'nt':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')

from kernel.core.kernel import MicroKernel


async def demo_basic_persistence():
    """基础持久化演示"""
    print("=" * 60)
    print("💾 演示 1: 基础配置持久化")
    print("=" * 60)
    print()

    config_file = Path("data/config_demo.json")
    config_file.parent.mkdir(exist_ok=True)

    # 先清理旧文件
    if config_file.exists():
        config_file.unlink()

    # 创建带文件持久化的内核
    kernel = MicroKernel(
        config_backend="file",
        config_path=str(config_file),
        config_format="json",
        auto_save=True,
    )

    print(f"配置文件：{config_file}")
    print()

    # 设置一些配置
    print("设置配置...")
    kernel.config.set("llm.api_key", "sk-test-12345")
    kernel.config.set("llm.default_model", "gpt-3.5-turbo")
    kernel.config.set("llm.timeout", 60)
    kernel.config.set("mqtt.broker", "localhost:1883")
    kernel.config.set("mqtt.username", "admin")
    kernel.config.set("monitoring.interval", 30)

    print("  ✓ 已设置 llm.* 和 mqtt.* 配置项")
    print()

    # 验证文件已创建
    print("验证文件内容...")
    with open(config_file, "r", encoding="utf-8") as f:
        saved_data = json.load(f)
    print(f"  文件大小：{os.path.getsize(config_file)} bytes")
    print(f"  配置项数：{len(saved_data)}")
    for k, v in saved_data.items():
        print(f"    {k} = {v}")
    print()

    # 演示命名空间
    print("命名空间隔离演示：")
    llm_config = kernel.config.get_namespace("llm")
    print(f"  llm.api_key = {llm_config.get('api_key')}")
    print(f"  llm.default_model = {llm_config.get('default_model')}")
    print()

    # 新内核加载同一文件
    print("新建内核，自动加载配置文件...")
    kernel2 = MicroKernel(
        config_backend="file",
        config_path=str(config_file),
        config_format="json",
    )
    print(f"  加载成功：llm.api_key = {kernel2.config.get('llm.api_key')}")
    print()

    # 清理
    if config_file.exists():
        config_file.unlink()
    print("✓ 持久化演示完成")
    print()


async def demo_watcher_notification():
    """配置变更通知演示"""
    print("=" * 60)
    print("🔔 演示 2: 配置变更 Watcher 通知")
    print("=" * 60)
    print()

    config_file = Path("data/config_watcher.json")
    config_file.parent.mkdir(exist_ok=True)
    if config_file.exists():
        config_file.unlink()

    kernel = MicroKernel(
        config_backend="file",
        config_path=str(config_file),
        auto_save=True,
    )

    # 注册 watcher
    notifications = []

    def on_llm_change(key, value):
        notifications.append(("llm", key, value))
        print(f"  [WATCHER] {key} 变更为: {value}")

    def on_mqtt_change(key, value):
        notifications.append(("mqtt", key, value))
        print(f"  [WATCHER] {key} 变更为: {value}")

    watcher1 = kernel.config.watch("llm.*", on_llm_change)
    watcher2 = kernel.config.watch("mqtt.*", on_mqtt_change)
    print("已注册 2 个 watcher")
    print()

    # 触发变更
    print("修改配置（触发 watcher）：")
    kernel.config.set("llm.api_key", "sk-new-key-abc")
    kernel.config.set("mqtt.broker", "mqtt.example.com:1883")
    kernel.config.set("monitoring.interval", 60)  # 不匹配任何 watcher
    print()

    print(f"触发通知数：{len(notifications)}")
    print(f"  llm 前缀: {sum(1 for n in notifications if n[0] == 'llm')} 次")
    print(f"  mqtt 前缀: {sum(1 for n in notifications if n[0] == 'mqtt')} 次")
    print()

    # 取消 watcher
    kernel.config.unwatch(watcher1)
    notifications.clear()

    print("取消 llm.* watcher 后修改配置：")
    kernel.config.set("llm.timeout", 120)
    kernel.config.set("mqtt.password", "secret")
    print(f"  现在只触发 mqtt watcher，通知数：{len(notifications)}")
    print()

    # 清理
    if config_file.exists():
        config_file.unlink()
    print("✓ Watcher 演示完成")
    print()


async def demo_hot_reload():
    """热重载演示（核心功能）"""
    print("=" * 60)
    print("🔥 演示 3: 文件热重载")
    print("=" * 60)
    print()

    config_file = Path("data/config_hotreload.json")
    config_file.parent.mkdir(exist_ok=True)

    # 先写入初始配置
    initial_config = {
        "llm.api_key": "sk-initial-key",
        "llm.default_model": "gpt-3.5-turbo",
        "mqtt.broker": "localhost:1883",
    }
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(initial_config, f, indent=2)

    print("初始配置文件已创建")
    print()

    # 创建内核并启用热重载
    kernel = MicroKernel(
        config_backend="file",
        config_path=str(config_file),
        auto_save=True,
        hot_reload=True,
    )

    print(f"热重载状态：{'已启用' if kernel.config.has_hotreload else '未启用'}")
    print()

    # 注册 watcher
    def on_change(key, value):
        print(f"  [变更通知] {key} = {value}")

    kernel.config.watch("*", on_change)

    # 读取初始值
    print(f"初始值: llm.api_key = {kernel.config.get('llm.api_key')}")
    print()

    # 外部修改配置文件（模拟用户手动编辑）
    print("用户外部修改配置文件...")
    modified_config = {
        "llm.api_key": "sk-CHANGED-BY-USER",  # 修改
        "llm.default_model": "gpt-4",  # 修改
        "llm.temperature": 0.7,  # 新增
        "mqtt.broker": "localhost:1883",  # 不变
        # 删除 mqtt.username（之前没有，所以不用删）
    }
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(modified_config, f, indent=2)
    print("  ✓ 文件已修改")
    print()

    # 等待热重载检测（需要等至少 1 秒检测间隔）
    print("等待热重载检测 (1.5秒)...")
    await asyncio.sleep(1.5)
    print()

    # 读取新值
    print(f"热重载后:")
    print(f"  llm.api_key = {kernel.config.get('llm.api_key')}")
    print(f"  llm.default_model = {kernel.config.get('llm.default_model')}")
    print(f"  llm.temperature = {kernel.config.get('llm.temperature')}")
    print()

    # 禁用热重载
    kernel.config.disable_hotreload()
    print(f"热重载状态：{'已启用' if kernel.config.has_hotreload else '未启用'}")
    print()

    # 清理
    if config_file.exists():
        config_file.unlink()
    print("✓ 热重载演示完成")
    print()


async def demo_yaml_format():
    """YAML 格式演示"""
    print("=" * 60)
    print("📄 演示 4: YAML 格式支持")
    print("=" * 60)
    print()

    config_file = Path("data/config_demo.yaml")
    config_file.parent.mkdir(exist_ok=True)
    if config_file.exists():
        config_file.unlink()

    try:
        kernel = MicroKernel(
            config_backend="file",
            config_path=str(config_file),
            config_format="yaml",
            auto_save=True,
        )

        # 设置配置
        kernel.config.set("database.host", "localhost")
        kernel.config.set("database.port", 5432)
        kernel.config.set("features.enabled", ["rag", "llm", "mqtt"])
        kernel.config.set("features.timeout", 30.5)
        kernel.config.set("debug", True)

        print("配置已写入 YAML 文件")
        print(f"文件路径：{config_file}")
        print()
        print("文件内容：")
        print("-" * 60)
        with open(config_file, "r", encoding="utf-8") as f:
            print(f.read())
        print("-" * 60)
        print()

        # 重新加载验证
        kernel2 = MicroKernel(
            config_backend="file",
            config_path=str(config_file),
            config_format="yaml",
        )
        print(f"重新加载验证：")
        print(f"  database.host = {kernel2.config.get('database.host')}")
        print(f"  database.port = {kernel2.config.get('database.port')}")
        print(f"  features.enabled = {kernel2.config.get('features.enabled')}")
        print()

        # 清理
        if config_file.exists():
            config_file.unlink()

        print("✓ YAML 格式演示完成")
        print()

    except ImportError:
        print("⚠ PyYAML 未安装，跳过 YAML 演示")
        print("  安装命令：pip install pyyaml")
        print()


async def demo_integration_with_plugins():
    """插件集成演示"""
    print("=" * 60)
    print("🔌 演示 5: 插件 + 配置持久化集成")
    print("=" * 60)
    print()

    config_file = Path("data/config_plugin_demo.json")
    config_file.parent.mkdir(exist_ok=True)
    if config_file.exists():
        config_file.unlink()

    # 先配置好 OpenAI API Key
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump({
            "llm.api_key": os.getenv("OPENAI_API_KEY", "sk-configured-from-file"),
            "llm.default_model": "gpt-3.5-turbo",
            "llm.timeout": 60,
        }, f, indent=2)

    # 创建内核，自动加载配置
    kernel = MicroKernel(
        config_backend="file",
        config_path=str(config_file),
        hot_reload=True,
    )

    # 注册 OpenAI 插件（插件从内核配置读取 API Key）
    from kernel.plugins.openai_plugin import OpenAIPlugin
    llm_plugin = OpenAIPlugin()
    await kernel.install_plugin(llm_plugin)
    await kernel.start()

    print("内核 + 插件启动完成")
    print(f"  配置来自：{config_file}")
    print(f"  插件读取：llm.default_model = {kernel.config.get('llm.default_model')}")
    print()

    # 现在，用户可以直接编辑配置文件，变更会自动生效！
    print("插件已从配置文件加载参数")
    print()

    # 演示：运行时修改配置（不需要重启插件）
    print("运行时修改 llm.default_model 配置...")
    kernel.config.set("llm.default_model", "gpt-4")
    print("  ✓ 插件后续调用会使用新配置")
    print()

    await kernel.stop()

    # 清理
    if config_file.exists():
        config_file.unlink()

    print("✓ 插件集成演示完成")
    print()


async def main():
    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║                AI 盒子 - 配置持久化演示                    ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()

    # 运行所有演示
    await demo_basic_persistence()
    await demo_watcher_notification()
    await demo_hot_reload()
    await demo_yaml_format()
    await demo_integration_with_plugins()

    print("=" * 60)
    print("✅ 所有演示完成！")
    print()
    print("核心功能总结：")
    print("  ✓ 配置自动保存到磁盘")
    print("  ✓ 启动时自动加载配置文件")
    print("  ✓ 支持 JSON / YAML 格式")
    print("  ✓ 支持命名空间隔离")
    print("  ✓ 支持通配符模式监听")
    print("  ✓ 外部修改文件自动热重载")
    print("  ✓ 插件从内核配置读取参数")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
