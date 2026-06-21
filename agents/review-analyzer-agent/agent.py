"""评价分析 Agent - ReviewAnalyzerAgent

负责分析商品评价，包括情感分析、差评识别、词云生成等
"""
import json
import sys
from pathlib import Path
from typing import List, Dict, Any
from collections import Counter

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from shared.models.product import Product, Review
from shared.utils.logger import AgentLogger
from shared.utils.api_client import ClaudeAPIClient
from shared.utils.config_loader import load_agent_config
from shared.constants.keywords import NEGATIVE_KEYWORDS, POSITIVE_KEYWORDS, FAKE_REVIEW_PATTERNS


class ReviewAnalyzerAgent:
    """评价分析器 Agent"""

    def __init__(self, config_path: str = None):
        """初始化分析器"""
        self.logger = AgentLogger("ReviewAnalyzerAgent", log_dir=str(project_root / "logs"))
        self.logger.info("初始化 ReviewAnalyzerAgent...")

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

        self.logger.info("ReviewAnalyzerAgent 初始化完成")

    def analyze_reviews(self, products: List[Product]) -> Dict[str, Any]:
        """
        分析所有商品的评价

        Args:
            products: 商品列表

        Returns:
            分析结果字典
        """
        self.logger.info(f"开始分析 {len(products)} 个商品的评价...")

        results = {}

        for product in products:
            product_key = f"{product.platform}_{product.product_id}"
            self.logger.info(f"分析商品: {product.title}")

            # 分析单个商品的评价
            analysis = self._analyze_product_reviews(product)
            results[product_key] = analysis

        self.logger.info("评价分析完成")
        return results

    def _analyze_product_reviews(self, product: Product) -> Dict[str, Any]:
        """分析单个商品的评价"""
        reviews = product.reviews

        if not reviews:
            return {
                "product_title": product.title,
                "platform": product.platform,
                "sentiment_summary": {"positive": 0, "neutral": 0, "negative": 0},
                "negative_keywords": [],
                "fake_review_detected": False,
                "risk_level": "unknown",
                "key_issues": [],
                "total_reviews": 0,
                "positive_rate": product.positive_rate
            }

        # 1. 情感分析
        sentiment_summary = self._sentiment_analysis(reviews)

        # 2. 差评关键词提取
        negative_keywords = self._extract_negative_keywords(reviews)

        # 3. 刷评检测
        fake_review_detected = self._detect_fake_reviews(reviews)

        # 4. 风险等级评估
        risk_level = self._assess_risk_level(
            sentiment_summary,
            negative_keywords,
            fake_review_detected,
            product.positive_rate
        )

        # 5. 关键问题提取
        key_issues = self._extract_key_issues(negative_keywords)

        return {
            "product_title": product.title,
            "platform": product.platform,
            "total_reviews": len(reviews),
            "sentiment_summary": sentiment_summary,
            "negative_keywords": negative_keywords,
            "fake_review_detected": fake_review_detected,
            "risk_level": risk_level,
            "key_issues": key_issues,
            "positive_rate": product.positive_rate
        }

    def _sentiment_analysis(self, reviews: List[Review]) -> Dict[str, int]:
        """情感分析：统计正面、中性、负面评价"""
        sentiment_counts = {"positive": 0, "neutral": 0, "negative": 0}

        for review in reviews:
            # 基于评分的简单情感分析
            if review.rating >= 4.5:
                sentiment_counts["positive"] += 1
            elif review.rating >= 3.0:
                sentiment_counts["neutral"] += 1
            else:
                sentiment_counts["negative"] += 1

        return sentiment_counts

    def _extract_negative_keywords(self, reviews: List[Review]) -> List[Dict[str, Any]]:
        """提取差评关键词"""
        found_keywords = []

        for review in reviews:
            if review.rating < 3.0:  # 只分析差评
                content = review.content

                for category, keywords in NEGATIVE_KEYWORDS.items():
                    for keyword in keywords:
                        if keyword in content:
                            found_keywords.append({
                                "keyword": keyword,
                                "category": category,
                                "review_content": content[:50] + "...",
                                "rating": review.rating
                            })

        return found_keywords

    def _detect_fake_reviews(self, reviews: List[Review]) -> bool:
        """检测是否存在刷评行为"""
        fake_patterns_found = 0

        for review in reviews:
            content = review.content.lower()

            for pattern in FAKE_REVIEW_PATTERNS:
                if pattern in content:
                    fake_patterns_found += 1
                    break

        # 如果超过 20% 的评价包含刷评关键词，判定为可疑
        if len(reviews) > 0 and fake_patterns_found / len(reviews) > 0.2:
            return True

        return False

    def _assess_risk_level(
        self,
        sentiment_summary: Dict[str, int],
        negative_keywords: List[Dict],
        fake_review_detected: bool,
        positive_rate: float
    ) -> str:
        """评估风险等级"""
        risk_score = 0

        # 负面评价比例
        total = sum(sentiment_summary.values())
        if total > 0:
            negative_ratio = sentiment_summary["negative"] / total
            if negative_ratio > 0.2:
                risk_score += 2
            elif negative_ratio > 0.1:
                risk_score += 1

        # 严重问题关键词
        serious_keywords = [kw for kw in negative_keywords if kw['category'] == '严重问题']
        if len(serious_keywords) > 0:
            risk_score += 3

        # 刷评检测
        if fake_review_detected:
            risk_score += 2

        # 好评率过低
        if positive_rate < 0.9:
            risk_score += 1

        # 判定风险等级
        if risk_score >= 5:
            return "high"
        elif risk_score >= 3:
            return "medium"
        else:
            return "low"

    def _extract_key_issues(self, negative_keywords: List[Dict]) -> List[str]:
        """提取关键问题"""
        if not negative_keywords:
            return []

        # 统计问题类别
        category_counter = Counter([kw['category'] for kw in negative_keywords])

        # 返回出现次数最多的前 3 个问题类别
        top_issues = [cat for cat, count in category_counter.most_common(3)]

        return top_issues

    def generate_word_cloud_data(self, products: List[Product]) -> Dict[str, int]:
        """
        生成词云数据（统计高频关键词）

        Args:
            products: 商品列表

        Returns:
            词频字典 {"关键词": 出现次数}
        """
        word_freq = Counter()

        for product in products:
            for review in product.reviews:
                # 简单的关键词提取（实际项目中可使用 jieba 分词）
                content = review.content

                # 统计差评关键词
                for category, keywords in NEGATIVE_KEYWORDS.items():
                    for keyword in keywords:
                        if keyword in content:
                            word_freq[keyword] += 1

        return dict(word_freq.most_common(20))


if __name__ == "__main__":
    # 测试代码
    from agents.scraper_agent.agent import ScraperAgent

    # 1. 先抓取数据
    scraper = ScraperAgent()
    products = scraper.fetch_products("iPhone 15 Pro", platforms=['xianyu', 'taobao'])

    # 2. 分析评价
    analyzer = ReviewAnalyzerAgent()
    results = analyzer.analyze_reviews(products)

    # 3. 打印结果
    print("\n=== 评价分析结果 ===")
    for product_key, analysis in results.items():
        print(f"\n商品: {analysis['product_title']}")
        print(f"平台: {analysis['platform']}")
        print(f"风险等级: {analysis['risk_level']}")
        print(f"情感分布: {analysis['sentiment_summary']}")
        print(f"关键问题: {analysis['key_issues']}")

    # 4. 生成词云数据
    word_cloud_data = analyzer.generate_word_cloud_data(products)
    print(f"\n=== 高频差评关键词 ===")
    for word, freq in list(word_cloud_data.items())[:10]:
        print(f"{word}: {freq}")
