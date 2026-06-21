"""价格监控 Agent - PriceMonitorAgent

负责价格对比、性价比计算、历史价格追踪
"""
import json
import sys
import sqlite3
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from shared.models.product import Product
from shared.utils.logger import AgentLogger
from shared.utils.api_client import ClaudeAPIClient
from shared.utils.config_loader import load_agent_config


class PriceMonitorAgent:
    """价格监控器 Agent"""

    def __init__(self, config_path: str = None):
        """初始化监控器"""
        self.logger = AgentLogger("PriceMonitorAgent", log_dir=str(project_root / "logs"))
        self.logger.info("初始化 PriceMonitorAgent...")

        # 加载配置
        if config_path is None:
            config_path = project_root / "config" / "agent_config.json"

        agent_config = load_agent_config(config_path)

        # 初始化 Claude API 客户端
        api_config = agent_config['api']
        self.api_client = ClaudeAPIClient(
            api_key=api_config['api_key'],
            base_url=api_config['base_url'],
            model=api_config['model']
        )

        # 初始化数据库
        self.db_path = project_root / "data" / "database" / "price_history.db"
        self._init_database()

        self.logger.info("PriceMonitorAgent 初始化完成")

    def _init_database(self):
        """初始化价格历史数据库"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id TEXT NOT NULL,
                platform TEXT NOT NULL,
                title TEXT,
                price REAL NOT NULL,
                seller_rating REAL,
                timestamp TEXT NOT NULL
            )
        ''')

        conn.commit()
        conn.close()

        self.logger.info(f"数据库初始化完成: {self.db_path}")

    def monitor_prices(self, products: List[Product]) -> Dict[str, Any]:
        """
        监控商品价格

        Args:
            products: 商品列表

        Returns:
            价格分析结果
        """
        self.logger.info(f"开始监控 {len(products)} 个商品的价格...")

        # 1. 保存当前价格到数据库
        self._save_prices(products)

        # 2. 价格对比
        price_comparison = self._compare_prices(products)

        # 3. 性价比计算
        value_ranking = self._calculate_value_ranking(products)

        # 4. 价格预警（检测异常低价或高价）
        price_alerts = self._detect_price_alerts(products, price_comparison)

        results = {
            "price_comparison": price_comparison,
            "value_ranking": value_ranking,
            "price_alerts": price_alerts,
            "best_deal": value_ranking[0] if value_ranking else None
        }

        self.logger.info("价格监控完成")
        return results

    def _save_prices(self, products: List[Product]):
        """保存价格到历史数据库"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        timestamp = datetime.now().isoformat()

        for product in products:
            cursor.execute('''
                INSERT INTO price_history (product_id, platform, title, price, seller_rating, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                product.product_id,
                product.platform,
                product.title,
                product.price,
                product.seller.rating if product.seller else None,
                timestamp
            ))

        conn.commit()
        conn.close()

        self.logger.info(f"保存了 {len(products)} 条价格记录")

    def _compare_prices(self, products: List[Product]) -> Dict[str, Any]:
        """价格对比分析"""
        if not products:
            return {}

        prices = [p.price for p in products]
        min_price = min(prices)
        max_price = max(prices)
        avg_price = sum(prices) / len(prices)

        # 找到最便宜和最贵的商品
        cheapest = min(products, key=lambda p: p.price)
        most_expensive = max(products, key=lambda p: p.price)

        return {
            "min_price": min_price,
            "max_price": max_price,
            "avg_price": round(avg_price, 2),
            "price_range": round(max_price - min_price, 2),
            "cheapest_product": {
                "title": cheapest.title,
                "price": cheapest.price,
                "platform": cheapest.platform
            },
            "most_expensive_product": {
                "title": most_expensive.title,
                "price": most_expensive.price,
                "platform": most_expensive.platform
            }
        }

    def _calculate_value_ranking(self, products: List[Product]) -> List[Dict[str, Any]]:
        """
        计算性价比排名

        性价比公式: score = (seller_rating * review_score * sales_factor) / price
        """
        value_scores = []

        for product in products:
            # 卖家评分 (0-5)
            seller_rating = product.seller.rating if product.seller else 3.0

            # 评价分数 (好评率)
            review_score = product.positive_rate

            # 销量因子 (取对数，避免销量差异过大)
            import math
            sales_factor = math.log10(product.sales + 1) if product.sales > 0 else 0

            # 计算性价比得分
            value_score = (seller_rating * review_score * (1 + sales_factor * 0.1)) / product.price

            value_scores.append({
                "product_id": product.product_id,
                "title": product.title,
                "platform": product.platform,
                "price": product.price,
                "value_score": round(value_score * 10000, 2),  # 放大便于展示
                "seller_rating": seller_rating,
                "positive_rate": review_score,
                "sales": product.sales
            })

        # 按性价比排序
        value_scores.sort(key=lambda x: x['value_score'], reverse=True)

        return value_scores

    def _detect_price_alerts(self, products: List[Product], price_comparison: Dict) -> List[Dict[str, str]]:
        """检测价格预警"""
        alerts = []

        avg_price = price_comparison.get('avg_price', 0)

        for product in products:
            # 价格异常低（低于平均价 15%）
            if product.price < avg_price * 0.85:
                alerts.append({
                    "type": "low_price",
                    "level": "warning",
                    "product": product.title,
                    "platform": product.platform,
                    "message": f"价格异常低（¥{product.price}），低于平均价 {round((1 - product.price/avg_price) * 100, 1)}%，请注意商品真伪"
                })

            # 价格异常高（高于平均价 20%）
            if product.price > avg_price * 1.2:
                alerts.append({
                    "type": "high_price",
                    "level": "info",
                    "product": product.title,
                    "platform": product.platform,
                    "message": f"价格较高（¥{product.price}），高于平均价 {round((product.price/avg_price - 1) * 100, 1)}%"
                })

        return alerts

    def get_price_history(self, product_id: str, days: int = 30) -> List[Dict[str, Any]]:
        """
        获取商品的历史价格

        Args:
            product_id: 商品 ID
            days: 查询天数

        Returns:
            历史价格列表
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute('''
            SELECT platform, price, timestamp
            FROM price_history
            WHERE product_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (product_id, days * 24))  # 假设每小时记录一次

        rows = cursor.fetchall()
        conn.close()

        history = []
        for row in rows:
            history.append({
                "platform": row[0],
                "price": row[1],
                "timestamp": row[2]
            })

        return history


if __name__ == "__main__":
    # 测试代码
    from agents.scraper_agent.agent import ScraperAgent

    # 1. 先抓取数据
    scraper = ScraperAgent()
    products = scraper.fetch_products("iPhone 15 Pro", platforms=['xianyu', 'taobao'])

    # 2. 价格监控
    monitor = PriceMonitorAgent()
    results = monitor.monitor_prices(products)

    # 3. 打印结果
    print("\n=== 价格对比 ===")
    comparison = results['price_comparison']
    print(f"最低价: ¥{comparison['min_price']}")
    print(f"最高价: ¥{comparison['max_price']}")
    print(f"平均价: ¥{comparison['avg_price']}")
    print(f"价格区间: ¥{comparison['price_range']}")

    print("\n=== 性价比排名 ===")
    for i, item in enumerate(results['value_ranking'][:3], 1):
        print(f"{i}. [{item['platform']}] {item['title']}")
        print(f"   价格: ¥{item['price']}, 性价比得分: {item['value_score']}")

    print("\n=== 价格预警 ===")
    for alert in results['price_alerts']:
        print(f"[{alert['level']}] {alert['message']}")
