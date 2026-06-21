"""Multi-Agent 协调器 - Coordinator

负责协调所有子 Agent 的工作流程
"""
import json
import sys
from pathlib import Path
from typing import List, Dict, Any
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from shared.utils.logger import AgentLogger
from shared.models.product import Product
from shared.utils.config_loader import load_agent_config
from shared.utils.skill_loader import get_skill_loader

# 导入各个 Agent（目录名含连字符，需用 importlib 加载）
import importlib.util

def _load_agent_class(agent_dir: str, class_name: str):
    """从指定目录加载 Agent 类"""
    agent_path = project_root / "agents" / agent_dir / "__init__.py"
    spec = importlib.util.spec_from_file_location(agent_dir, str(agent_path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[agent_dir] = module
    spec.loader.exec_module(module)
    return getattr(module, class_name)

ScraperAgent = _load_agent_class("scraper-agent", "ScraperAgent")
ReviewAnalyzerAgent = _load_agent_class("review-analyzer-agent", "ReviewAnalyzerAgent")
PriceMonitorAgent = _load_agent_class("price-monitor-agent", "PriceMonitorAgent")
ReportGeneratorAgent = _load_agent_class("report-generator-agent", "ReportGeneratorAgent")


class MultiAgentCoordinator:
    """Multi-Agent 系统协调器"""

    def __init__(self):
        """初始化协调器"""
        self.logger = AgentLogger("Coordinator", log_dir=str(project_root / "logs"))
        self.logger.info("=" * 50)
        self.logger.info("初始化 Multi-Agent 协调器...")
        self.logger.info("=" * 50)

        # 加载配置
        config_path = project_root / "config" / "agent_config.json"
        self.config = load_agent_config(config_path)

        workflow_path = project_root / "config" / "workflow_config.json"
        with open(workflow_path, 'r', encoding='utf-8-sig') as f:
            self.workflow = json.load(f)

        # 初始化所有子 Agent
        self.logger.info("正在初始化子 Agent...")
        self.agents = {
            'scraper': ScraperAgent(),
            'review_analyzer': ReviewAnalyzerAgent(),
            'price_monitor': PriceMonitorAgent(),
            'report_generator': ReportGeneratorAgent()
        }

        self.logger.info(f"成功初始化 {len(self.agents)} 个子 Agent")
        self.logger.info("Multi-Agent 系统就绪！")

        # 加载 Skills 系统
        skills_dir = project_root / "skills"
        self.skill_loader = get_skill_loader(skills_dir)
        skill_count = len(self.skill_loader.skills)
        self.logger.info(f"加载了 {skill_count} 个技能: {list(self.skill_loader.skills.keys())}")

    def execute_research(
        self,
        query: str,
        platforms: List[str] = None,
        sample_count: int = None,
        location: str = "",
        sort_order: str = "none",
        search_keywords: List[str] = None,
        category: str = "",
        sub_category: str = "",
        budget_min: float = None,
        budget_max: float = None,
        progress_callback=None
    ) -> Dict[str, Any]:
        """
        执行完整的购物调研流程

        Args:
            query: 搜索关键词（如 "iPhone 15 Pro"）
            platforms: 要搜索的平台列表（如 ['xianyu', 'taobao']）
            sample_count: 用户希望随机爬取的数量
            location: 地区筛选（如 福建、厦门）
            sort_order: 价格排序（none, price_asc, price_desc）
            search_keywords: AI 扩展的搜索关键词列表
            category: AI 识别的商品品类
            sub_category: AI 识别的商品细分类

        Returns:
            执行结果，包含报告路径和各阶段数据
        """
        self.logger.info("=" * 50)
        self.logger.info(f"🚀 开始执行购物调研任务")
        self.logger.info(f"📝 查询关键词: {query}")
        self.logger.info(f"🌐 目标平台: {platforms or '配置中启用的所有平台'}")
        self.logger.info(f"📍 地区: {location or '不限'}")
        self.logger.info(f"🎲 抽样数量: {sample_count or '默认'}")
        self.logger.info(f"💰 排序: {sort_order}")
        if search_keywords:
            self.logger.info(f"🔑 AI扩展关键词: {search_keywords}")
        if category:
            self.logger.info(f"📂 AI识别品类: {category}")
        if sub_category:
            self.logger.info(f"🧩 AI细分类: {sub_category}")
        if budget_min is not None or budget_max is not None:
            self.logger.info(
                f"💵 预算区间: {budget_min if budget_min is not None else '-'} ~ "
                f"{budget_max if budget_max is not None else '-'}"
            )
        self.logger.info("=" * 50)

        start_time = time.time()
        results = {}

        try:
            # 按照 workflow 配置执行
            for step_config in self.workflow['workflow']:
                step_num = step_config['step']
                step_name = step_config['name']

                self.logger.info(f"\n{'='*50}")
                self.logger.info(f"📍 Step {step_num}: {step_name}")
                self.logger.info(f"{'='*50}")

                if step_num == 1:
                    # 数据采集
                    results['products'] = self._execute_scraper(
                        query,
                        platforms,
                        sample_count=sample_count,
                        location=location,
                        sort_order=sort_order,
                        search_keywords=search_keywords,
                        category=category,
                        sub_category=sub_category,
                        budget_min=budget_min,
                        budget_max=budget_max,
                        progress_callback=progress_callback
                    )
                    results['crawl_meta'] = getattr(self.agents['scraper'], 'last_crawl_meta', {})

                elif step_num == 2:
                    # 并行执行评价分析和价格监控
                    if step_config.get('parallel'):
                        self.logger.info("⚡ 并行执行分析任务...")
                        results.update(self._execute_parallel_analysis(results['products']))
                    else:
                        results['review_analysis'] = self._execute_review_analyzer(results['products'])
                        results['price_monitoring'] = self._execute_price_monitor(results['products'])

                elif step_num == 3:
                    # 生成报告
                    report_artifacts = self._execute_report_generator(
                        query,
                        results['products'],
                        results['review_analysis'],
                        results['price_monitoring']
                    )
                    results['report_path'] = report_artifacts.get('report_path')
                    results['charts'] = report_artifacts.get('charts', {})

            # 执行完成
            elapsed_time = time.time() - start_time

            self.logger.info("\n" + "=" * 50)
            self.logger.info(f"✅ 任务完成！总耗时: {elapsed_time:.2f} 秒")
            self.logger.info("=" * 50)

            return {
                'success': True,
                'query': query,
                'platforms': platforms,
                'sample_count': sample_count,
                'location': location,
                'sort_order': sort_order,
                'budget_min': budget_min,
                'budget_max': budget_max,
                'elapsed_time': elapsed_time,
                'report_path': results.get('report_path'),
                'products_count': len(results.get('products', [])),
                'crawl_meta': results.get('crawl_meta', {}),
                'results': results
            }

        except Exception as e:
            self.logger.error(f"❌ 任务执行失败: {str(e)}")
            # 记录完整的异常堆栈
            import traceback
            self.logger.error(f"详细错误信息:\n{traceback.format_exc()}")
            crawl_meta = results.get('crawl_meta') or getattr(self.agents['scraper'], 'last_crawl_meta', {})
            return {
                'success': False,
                'error': str(e),
                'crawl_meta': crawl_meta,
                'results': {
                    'crawl_meta': crawl_meta
                } if crawl_meta else {}
            }

    def _execute_scraper(
        self,
        query: str,
        platforms: List[str],
        sample_count: int = None,
        location: str = "",
        sort_order: str = "none",
        search_keywords: List[str] = None,
        category: str = "",
        sub_category: str = "",
        budget_min: float = None,
        budget_max: float = None,
        progress_callback=None
    ) -> List[Product]:
        """执行数据采集"""
        self.logger.info(f"🔍 Agent 1 (ScraperAgent) 开始工作...")

        agent = self.agents['scraper']
        products = agent.fetch_products(
            query,
            platforms,
            max_results_per_platform=sample_count,
            location=location,
            sort_order=sort_order,
            search_keywords=search_keywords,
            category=category,
            sub_category=sub_category,
            budget_min=budget_min,
            budget_max=budget_max,
            progress_callback=progress_callback
        )

        self.logger.info(f"✅ Agent 1 完成，获取了 {len(products)} 个商品")
        return products

    def _execute_review_analyzer(self, products: List[Product]) -> Dict[str, Any]:
        """执行评价分析"""
        self.logger.info(f"💬 Agent 2 (ReviewAnalyzerAgent) 开始工作...")

        agent = self.agents['review_analyzer']
        results = agent.analyze_reviews(products)

        self.logger.info(f"✅ Agent 2 完成，分析了 {len(products)} 个商品的评价")
        return results

    def _execute_price_monitor(self, products: List[Product]) -> Dict[str, Any]:
        """执行价格监控"""
        self.logger.info(f"💰 Agent 3 (PriceMonitorAgent) 开始工作...")

        agent = self.agents['price_monitor']
        results = agent.monitor_prices(products)

        self.logger.info(f"✅ Agent 3 完成，完成价格分析")
        return results

    def _execute_report_generator(
        self,
        query: str,
        products: List[Product],
        review_analysis: Dict[str, Any],
        price_monitoring: Dict[str, Any]
    ) -> Dict[str, Any]:
        """执行报告生成"""
        self.logger.info(f"📊 Agent 4 (ReportGeneratorAgent) 开始工作...")

        agent = self.agents['report_generator']
        report_artifacts = agent.generate_report(
            products,
            review_analysis,
            price_monitoring,
            query
        )

        self.logger.info(f"✅ Agent 4 完成，报告路径: {report_artifacts.get('report_path')}")
        return report_artifacts

    def _execute_parallel_analysis(self, products: List[Product]) -> Dict[str, Any]:
        """并行执行评价分析和价格监控"""
        results = {}

        with ThreadPoolExecutor(max_workers=2) as executor:
            # 提交两个任务
            future_review = executor.submit(self._execute_review_analyzer, products)
            future_price = executor.submit(self._execute_price_monitor, products)

            # 等待完成
            for future in as_completed([future_review, future_price]):
                if future == future_review:
                    results['review_analysis'] = future.result()
                elif future == future_price:
                    results['price_monitoring'] = future.result()

        return results

    def print_summary(self, result: Dict[str, Any]):
        """打印执行摘要"""
        if not result.get('success'):
            print(f"\n❌ 执行失败: {result.get('error')}")
            return

        print("\n" + "=" * 60)
        print("📊 执行摘要")
        print("=" * 60)
        print(f"查询关键词: {result['query']}")
        print(f"商品数量: {result['products_count']}")
        print(f"耗时: {result['elapsed_time']:.2f} 秒")
        print(f"报告路径: {result['report_path']}")
        print("=" * 60)


if __name__ == "__main__":
    # 测试协调器
    coordinator = MultiAgentCoordinator()

    # 执行购物调研
    result = coordinator.execute_research(
        query="iPhone 15 Pro",
        platforms=['xianyu', 'taobao']
    )

    # 打印摘要
    coordinator.print_summary(result)
