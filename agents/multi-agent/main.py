"""主入口文件 - main.py

Multi-Agent 购物调研系统的命令行入口
"""
import sys
import argparse
from pathlib import Path

# 修复 Windows GBK 编码问题
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from coordinator import MultiAgentCoordinator


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='Multi-Agent 购物调研系统',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 基本查询
  python main.py --query "iPhone 15 Pro"

  # 指定平台
  python main.py --query "小米 14" --platforms xianyu taobao

  # 只查询单个平台
  python main.py --query "MacBook Air" --platforms xianyu
        """
    )

    parser.add_argument(
        '--query', '-q',
        type=str,
        required=True,
        help='搜索关键词（如 "iPhone 15 Pro"）'
    )

    parser.add_argument(
        '--platforms', '-p',
        nargs='+',
        choices=['xianyu', 'taobao', 'jd', 'pdd'],
        help='要搜索的平台（可多选）'
    )

    parser.add_argument(
        '--sample-count', '-n',
        type=int,
        default=50,
        help='随机抓取数量'
    )

    parser.add_argument(
        '--location', '-l',
        type=str,
        default='',
        help='地区范围，如 福建、厦门、福州'
    )

    parser.add_argument(
        '--sort-order',
        choices=['none', 'price_asc', 'price_desc'],
        default='none',
        help='价格排序方式'
    )

    parser.add_argument(
        '--budget-min',
        type=float,
        default=None,
        help='最低价格'
    )

    parser.add_argument(
        '--budget-max',
        type=float,
        default=None,
        help='最高价格'
    )

    args = parser.parse_args()

    # 初始化协调器
    print("\n🤖 Multi-Agent 购物调研系统")
    print("=" * 60)

    coordinator = MultiAgentCoordinator()

    # 执行调研
    result = coordinator.execute_research(
        query=args.query,
        platforms=args.platforms,
        sample_count=args.sample_count,
        location=args.location,
        sort_order=args.sort_order,
        budget_min=args.budget_min,
        budget_max=args.budget_max,
    )

    # 打印摘要
    coordinator.print_summary(result)

    # 如果成功，提示用户查看报告
    if result.get('success'):
        print(f"\n💡 提示: 请查看生成的报告和图表")
        print(f"   报告: {result['report_path']}")
        print(f"   图表: {project_root / 'reports' / 'charts'}\n")


if __name__ == "__main__":
    main()
