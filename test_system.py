"""快速测试脚本 - 验证 Multi-Agent 系统是否正常工作"""
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "agents" / "multi-agent"))

print("=" * 60)
print("🧪 Multi-Agent 系统测试")
print("=" * 60)

# 测试 1: 导入检查
print("\n[1/5] 测试模块导入...")
try:
    from shared.utils.logger import AgentLogger
    from shared.models.product import Product, Seller, Review
    from shared.constants.keywords import NEGATIVE_KEYWORDS
    print("✅ 共享模块导入成功")
except Exception as e:
    print(f"❌ 共享模块导入失败: {e}")
    sys.exit(1)

# 测试 2: 配置文件
print("\n[2/5] 检查配置文件...")
import json
try:
    config_files = [
        "config/agent_config.json",
        "config/platform_config.json",
        "config/workflow_config.json"
    ]
    for config_file in config_files:
        path = project_root / config_file
        with open(path, 'r', encoding='utf-8') as f:
            json.load(f)
        print(f"✅ {config_file} 加载成功")
except Exception as e:
    print(f"❌ 配置文件检查失败: {e}")
    sys.exit(1)

# 测试 3: Mock 数据
print("\n[3/5] 检查 Mock 数据...")
try:
    mock_files = [
        "data/mock_data/xianyu_products.json",
        "data/mock_data/taobao_products.json"
    ]
    for mock_file in mock_files:
        path = project_root / mock_file
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"✅ {mock_file} 加载成功 ({len(data)} 个商品)")
except Exception as e:
    print(f"❌ Mock 数据检查失败: {e}")
    sys.exit(1)

# 测试 4: Agent 初始化
print("\n[4/5] 测试 Agent 初始化...")
try:
    sys.path.insert(0, str(project_root / "agents" / "scraper-agent"))
    from agent import ScraperAgent

    scraper = ScraperAgent()
    print("✅ ScraperAgent 初始化成功")

    sys.path.insert(0, str(project_root / "agents" / "review-analyzer-agent"))
    from agent import ReviewAnalyzerAgent

    analyzer = ReviewAnalyzerAgent()
    print("✅ ReviewAnalyzerAgent 初始化成功")

    sys.path.insert(0, str(project_root / "agents" / "price-monitor-agent"))
    from agent import PriceMonitorAgent

    monitor = PriceMonitorAgent()
    print("✅ PriceMonitorAgent 初始化成功")

    sys.path.insert(0, str(project_root / "agents" / "report-generator-agent"))
    from agent import ReportGeneratorAgent

    generator = ReportGeneratorAgent()
    print("✅ ReportGeneratorAgent 初始化成功")

except Exception as e:
    print(f"❌ Agent 初始化失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 测试 5: 简单数据流测试
print("\n[5/5] 测试数据流...")
try:
    # 1. 抓取数据
    products = scraper.fetch_products("iPhone 15 Pro", platforms=['xianyu'])
    print(f"✅ 获取了 {len(products)} 个商品")

    # 2. 分析评价
    review_results = analyzer.analyze_reviews(products)
    print(f"✅ 完成评价分析")

    # 3. 监控价格
    price_results = monitor.monitor_prices(products)
    print(f"✅ 完成价格监控")

    print(f"\n价格范围: ¥{price_results['price_comparison']['min_price']} - ¥{price_results['price_comparison']['max_price']}")

except Exception as e:
    print(f"❌ 数据流测试失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 测试完成
print("\n" + "=" * 60)
print("✅ 所有测试通过！系统运行正常")
print("=" * 60)
print("\n💡 提示：运行以下命令开始使用：")
print("   python agents/multi-agent/main.py --query \"iPhone 15 Pro\"\n")
