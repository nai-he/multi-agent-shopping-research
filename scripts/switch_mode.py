"""切换爬虫模式配置"""
import json
from pathlib import Path

config_path = Path(__file__).parent.parent / "config" / "platform_config.json"

def switch_mode(mode: str):
    """切换爬虫模式"""
    if mode not in ["mock", "real"]:
        print(f"❌ 无效的模式: {mode}")
        print("   可选: mock, real")
        return

    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    old_mode = config['scraper_settings']['mode']
    config['scraper_settings']['mode'] = mode

    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    print(f"✅ 已切换爬虫模式: {old_mode} -> {mode}")
    print()

    if mode == "mock":
        print("📦 Mock 模式:")
        print("   - 使用本地 JSON 文件模拟数据")
        print("   - 快速响应，适合开发调试")
        print("   - 数据固定，不受网络影响")
    else:
        print("🌐 Real 模式:")
        print("   - 真实爬取网站数据")
        print("   - 搜索什么爬什么")
        print("   - 需要 Chrome 浏览器和网络")
        print("   - 适合演示和生产环境")


def show_status():
    """显示当前模式"""
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    mode = config['scraper_settings']['mode']
    max_products = config['scraper_settings']['max_products_per_platform']

    print("=" * 60)
    print("当前爬虫配置")
    print("=" * 60)
    print(f"模式: {mode}")
    print(f"每平台最大商品数: {max_products}")
    print(f"配置文件: {config_path}")
    print("=" * 60)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        show_status()
        print()
        print("使用方法:")
        print("  python switch_mode.py mock   # 切换到 Mock 模式")
        print("  python switch_mode.py real   # 切换到 Real 模式")
    else:
        mode = sys.argv[1].lower()
        switch_mode(mode)
