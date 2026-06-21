"""报告生成 Agent - ReportGeneratorAgent

负责生成 Markdown 报告和可视化图表
"""
import json
import re
import sys
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime
import matplotlib
matplotlib.use('Agg')  # 非交互式后端
import matplotlib.pyplot as plt
import seaborn as sns

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from shared.models.product import Product
from shared.utils.logger import AgentLogger
from shared.utils.api_client import ClaudeAPIClient
from shared.utils.config_loader import load_agent_config

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False


class ReportGeneratorAgent:
    """报告生成器 Agent"""

    def __init__(self, config_path: str = None):
        """初始化生成器"""
        self.logger = AgentLogger("ReportGeneratorAgent", log_dir=str(project_root / "logs"))
        self.logger.info("初始化 ReportGeneratorAgent...")

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

        self.charts_dir = project_root / "reports" / "charts"
        self.charts_dir.mkdir(parents=True, exist_ok=True)
        self.last_generated_charts: Dict[str, str] = {}

        self.logger.info("ReportGeneratorAgent 初始化完成")

    def generate_report(
        self,
        products: List[Product],
        review_analysis: Dict[str, Any],
        price_monitoring: Dict[str, Any],
        query: str
    ) -> Dict[str, Any]:
        """
        生成完整报告

        Args:
            products: 商品列表
            review_analysis: 评价分析结果
            price_monitoring: 价格监控结果
            query: 搜索关键词

        Returns:
            报告文件路径
        """
        self.logger.info(f"开始生成报告: {query}")

        # 1. 生成图表
        slug = self._build_report_slug(query)
        charts = self._generate_all_charts(products, review_analysis, price_monitoring, slug)
        self.last_generated_charts = charts

        # 2. 生成 Markdown 报告
        report_content = self._generate_markdown_report(
            query, products, review_analysis, price_monitoring, charts
        )

        # 3. 保存报告
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = project_root / "reports" / f"shopping_report_{timestamp}_{slug}.md"

        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report_content)

        self.logger.info(f"报告已生成: {report_file}")
        return {
            "report_path": str(report_file),
            "charts": charts,
        }

    def _generate_all_charts(
        self,
        products: List[Product],
        review_analysis: Dict[str, Any],
        price_monitoring: Dict[str, Any],
        slug: str
    ) -> Dict[str, str]:
        """生成所有图表"""
        self.logger.info("开始生成图表...")

        charts = {}

        # 1. 价格对比柱状图
        charts['price_comparison'] = self._chart_price_comparison(products, slug)

        # 2. 卖家信誉雷达图
        charts['seller_radar'] = self._chart_seller_radar(products, slug)

        # 3. 情感分析饼图
        charts['sentiment_pie'] = self._chart_sentiment_analysis(review_analysis, slug)

        # 4. 性价比对比柱状图
        charts['value_ranking'] = self._chart_value_ranking(price_monitoring, slug)

        # 5. 平台价格箱线图
        charts['platform_boxplot'] = self._chart_platform_boxplot(products, slug)

        self.logger.info(f"生成了 {len(charts)} 张图表")
        return charts

    def _chart_price_comparison(self, products: List[Product], slug: str) -> str:
        """图表1: 价格-数量分布折线图"""
        if not products:
            return ""

        import numpy as np

        prices = [p.price for p in products]

        # 自动计算合适的区间数量（10-20个区间）
        num_bins = max(10, min(20, int(len(prices) ** 0.5) * 2))
        bin_edges = np.linspace(min(prices), max(prices), num_bins + 1)
        bin_centers = [(bin_edges[i] + bin_edges[i+1]) / 2 for i in range(num_bins)]

        # 统计每个区间的商品数量
        counts = [0] * num_bins
        for p in prices:
            for i in range(num_bins):
                if bin_edges[i] <= p < bin_edges[i+1] or (i == num_bins - 1 and p == bin_edges[i+1]):
                    counts[i] += 1
                    break

        fig, ax1 = plt.subplots(figsize=(12, 6))

        # 折线 + 面积图
        ax1.fill_between(range(num_bins), counts, alpha=0.15, color='#3498DB')
        ax1.plot(range(num_bins), counts, color='#3498DB', linewidth=2.5, marker='o',
                 markersize=8, markerfacecolor='white', markeredgewidth=2,
                 markeredgecolor='#3498DB', zorder=3)

        # 在每个点上标数量
        for i, cnt in enumerate(counts):
            if cnt > 0:
                ax1.annotate(str(cnt), (i, cnt), textcoords="offset points",
                            xytext=(0, 12), ha='center', fontsize=10, fontweight='bold', color='#2C3E50')

        ax1.set_xlabel('价格区间 (¥)', fontsize=12)
        ax1.set_ylabel('商品数量', fontsize=12, color='#3498DB')
        ax1.tick_params(axis='y', labelcolor='#3498DB')

        # X 轴标签用价格区间
        bin_labels = [f'¥{bin_edges[i]:.0f}-{bin_edges[i+1]:.0f}' for i in range(num_bins)]
        ax1.set_xticks(range(num_bins))
        ax1.set_xticklabels(bin_labels, rotation=45, ha='right', fontsize=9)
        ax1.set_title('价格-数量分布折线图', fontsize=14, fontweight='bold')

        # 叠加累计占比曲线（右轴）
        ax2 = ax1.twinx()
        cumulative = np.cumsum(counts) / sum(counts) * 100
        ax2.plot(range(num_bins), cumulative, color='#E74C3C', linewidth=1.8,
                 linestyle='--', marker='s', markersize=5, alpha=0.7, zorder=2)
        ax2.set_ylabel('累计占比 (%)', fontsize=12, color='#E74C3C')
        ax2.tick_params(axis='y', labelcolor='#E74C3C')
        ax2.set_ylim(0, 105)

        # 图例
        from matplotlib.lines import Line2D
        legend_elements = [
            Line2D([0], [0], color='#3498DB', linewidth=2.5, marker='o', markersize=8,
                   markerfacecolor='white', markeredgewidth=2, label='商品数量'),
            Line2D([0], [0], color='#E74C3C', linewidth=1.8, linestyle='--', marker='s',
                   markersize=5, label='累计占比'),
        ]
        ax1.legend(handles=legend_elements, loc='upper right')

        ax1.grid(True, alpha=0.3, axis='y')

        plt.tight_layout()
        chart_file = self.charts_dir / f"{slug}_price_comparison.png"
        plt.savefig(chart_file, dpi=150, bbox_inches='tight')
        plt.close()

        return chart_file.name

    def _chart_seller_radar(self, products: List[Product], slug: str) -> str:
        """图表2: 卖家信誉雷达图"""
        if not products:
            return ""  # 没有商品时跳过图表生成

        import numpy as np

        fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(projection='polar'))

        categories = ['评分', '发货速度', '服务态度', '好评率', '销量(归一化)']
        num_vars = len(categories)

        angles = np.linspace(0, 2 * np.pi, num_vars, endpoint=False).tolist()
        angles += angles[:1]

        ax.set_theta_offset(np.pi / 2)
        ax.set_theta_direction(-1)
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(categories)

        # 为每个商品绘制雷达图
        for i, product in enumerate(products[:3]):  # 最多显示3个
            if not product.seller:
                continue

            values = [
                product.seller.rating / 5.0,  # 评分归一化到0-1
                (product.seller.ship_speed_score or 4.0) / 5.0,
                (product.seller.service_score or 4.0) / 5.0,
                product.positive_rate,
                min(product.sales / 10000, 1.0)  # 销量归一化
            ]
            values += values[:1]

            label = f"[{product.platform}] {product.title[:15]}..."
            ax.plot(angles, values, 'o-', linewidth=2, label=label)
            ax.fill(angles, values, alpha=0.15)

        ax.set_ylim(0, 1)
        ax.set_title('卖家信誉多维对比', size=14, fontweight='bold', pad=20)
        ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.0))

        plt.tight_layout()
        chart_file = self.charts_dir / f"{slug}_seller_radar.png"
        plt.savefig(chart_file, dpi=150, bbox_inches='tight')
        plt.close()

        return chart_file.name

    def _chart_sentiment_analysis(self, review_analysis: Dict[str, Any], slug: str) -> str:
        """图表3: 情感分析饼图"""
        fig, ax = plt.subplots(figsize=(8, 6))

        # 汇总所有商品的情感分析
        total_sentiment = {'positive': 0, 'neutral': 0, 'negative': 0}

        for product_key, analysis in review_analysis.items():
            sentiment = analysis.get('sentiment_summary', {})
            for key in total_sentiment:
                total_sentiment[key] += sentiment.get(key, 0)

        # 检查是否有数据
        total_count = sum(total_sentiment.values())
        if total_count == 0:
            # 没有数据时使用默认值
            total_sentiment = {'positive': 1, 'neutral': 0, 'negative': 0}

        labels = ['正面评价', '中性评价', '负面评价']
        sizes = [total_sentiment['positive'], total_sentiment['neutral'], total_sentiment['negative']]
        colors = ['#2ECC71', '#F39C12', '#E74C3C']
        explode = (0.05, 0, 0.05)

        wedges, texts, autotexts = ax.pie(
            sizes, explode=explode, labels=labels, colors=colors,
            autopct='%1.1f%%', startangle=90, textprops={'fontsize': 12}
        )

        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontweight('bold')

        ax.set_title('商品评价情感分布', fontsize=14, fontweight='bold')

        plt.tight_layout()
        chart_file = self.charts_dir / f"{slug}_sentiment_pie.png"
        plt.savefig(chart_file, dpi=150, bbox_inches='tight')
        plt.close()

        return chart_file.name

    def _chart_value_ranking(self, price_monitoring: Dict[str, Any], slug: str) -> str:
        """图表4: 性价比排名柱状图"""
        fig, ax = plt.subplots(figsize=(10, 6))

        value_ranking = price_monitoring.get('value_ranking', [])[:5]  # 前5名

        if not value_ranking:
            return ""

        titles = [item['title'][:20] + '...' for item in value_ranking]
        scores = [item['value_score'] for item in value_ranking]

        bars = ax.barh(range(len(titles)), scores, color='#3498DB', alpha=0.8)

        ax.set_yticks(range(len(titles)))
        ax.set_yticklabels(titles)
        ax.set_xlabel('性价比得分', fontsize=12)
        ax.set_title('商品性价比排名 Top 5', fontsize=14, fontweight='bold')

        # 在柱子上显示分数
        for i, (bar, score) in enumerate(zip(bars, scores)):
            width = bar.get_width()
            ax.text(width, bar.get_y() + bar.get_height()/2.,
                   f'{score:.1f}',
                   ha='left', va='center', fontsize=10)

        plt.tight_layout()
        chart_file = self.charts_dir / f"{slug}_value_ranking.png"
        plt.savefig(chart_file, dpi=150, bbox_inches='tight')
        plt.close()

        return chart_file.name

    def _chart_platform_boxplot(self, products: List[Product], slug: str) -> str:
        """图表5: 平台价格分布箱线图"""
        if not products:
            return ""  # 没有商品时跳过图表生成

        fig, ax = plt.subplots(figsize=(8, 6))

        # 按平台分组价格数据
        platform_prices = {}
        for product in products:
            if product.platform not in platform_prices:
                platform_prices[product.platform] = []
            platform_prices[product.platform].append(product.price)

        platforms = list(platform_prices.keys())
        data = [platform_prices[p] for p in platforms]

        bp = ax.boxplot(data, patch_artist=True)

        # 设置 x 轴标签
        ax.set_xticks(range(1, len(platforms) + 1))
        ax.set_xticklabels(platforms)

        # 美化箱线图
        colors = ['#FF6B6B', '#FF8800', '#E74C3C', '#9B59B6']
        for patch, color in zip(bp['boxes'], colors[:len(platforms)]):
            patch.set_facecolor(color)
            patch.set_alpha(0.6)

        ax.set_xlabel('平台', fontsize=12)
        ax.set_ylabel('价格 (¥)', fontsize=12)
        ax.set_title('各平台价格分布', fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3, axis='y')

        plt.tight_layout()
        chart_file = self.charts_dir / f"{slug}_platform_boxplot.png"
        plt.savefig(chart_file, dpi=150, bbox_inches='tight')
        plt.close()

        return chart_file.name

    def _generate_markdown_report(
        self,
        query: str,
        products: List[Product],
        review_analysis: Dict[str, Any],
        price_monitoring: Dict[str, Any],
        charts: Dict[str, str]
    ) -> str:
        """生成 Markdown 报告内容"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        report = f"""# 购物调研报告：{query}

**生成时间**: {timestamp}
**对比商品数**: {len(products)}
**分析平台**: {', '.join(set(p.platform for p in products))}

---

## 📊 价格对比分析

### 价格概览

"""

        comparison = price_monitoring.get('price_comparison', {})
        report += f"""| 指标 | 数值 |
|------|------|
| 最低价 | ¥{comparison.get('min_price', 0):.2f} |
| 最高价 | ¥{comparison.get('max_price', 0):.2f} |
| 平均价 | ¥{comparison.get('avg_price', 0):.2f} |
| 价格区间 | ¥{comparison.get('price_range', 0):.2f} |

"""

        if charts.get('price_comparison'):
            report += f"![价格-数量分布折线图](charts/{charts['price_comparison']})\n\n"

        # 商品明细表
        report += """### 商品明细

| 平台 | 商品标题 | 价格 | 卖家 | 信誉 | 销量 | 好评率 |
|------|---------|------|------|------|------|--------|
"""
        for p in products:
            seller_name = p.seller.name if p.seller else "未知"
            seller_rating = f"{p.seller.rating:.1f}⭐" if p.seller else "-"
            report += f"| {p.platform} | {p.title[:30]}... | ¥{p.price} | {seller_name} | {seller_rating} | {p.sales} | {p.positive_rate*100:.1f}% |\n"

        report += "\n---\n\n"

        # 性价比分析
        report += "## 💰 性价比分析\n\n"

        if charts.get('value_ranking'):
            report += f"![性价比排名](charts/{charts['value_ranking']})\n\n"

        best_deal = price_monitoring.get('best_deal')
        if best_deal:
            report += f"""### 🏆 最佳性价比推荐

**商品**: {best_deal['title']}
**平台**: {best_deal['platform']}
**价格**: ¥{best_deal['price']}
**性价比得分**: {best_deal['value_score']}

"""

        # 价格预警
        alerts = price_monitoring.get('price_alerts', [])
        if alerts:
            report += "### ⚠️ 价格预警\n\n"
            for alert in alerts:
                icon = "⚠️" if alert['level'] == 'warning' else "ℹ️"
                report += f"{icon} **{alert['product']}** ({alert['platform']}): {alert['message']}\n\n"

        report += "---\n\n"

        # 评价分析
        report += "## 💬 评价分析\n\n"

        if charts.get('sentiment_pie'):
            report += f"![情感分析](charts/{charts['sentiment_pie']})\n\n"

        for product_key, analysis in review_analysis.items():
            report += f"### {analysis['product_title']}\n\n"
            report += f"**平台**: {analysis['platform']}  \n"
            report += f"**风险等级**: "

            risk_level = analysis['risk_level']
            if risk_level == 'low':
                report += "🟢 低风险\n"
            elif risk_level == 'medium':
                report += "🟡 中风险\n"
            else:
                report += "🔴 高风险\n"

            sentiment = analysis['sentiment_summary']
            report += f"**评价分布**: 正面 {sentiment['positive']} / 中性 {sentiment['neutral']} / 负面 {sentiment['negative']}  \n"

            if analysis['key_issues']:
                report += f"**主要问题**: {', '.join(analysis['key_issues'])}  \n"

            report += "\n"

        if charts.get('seller_radar'):
            report += f"![卖家信誉对比](charts/{charts['seller_radar']})\n\n"

        report += "---\n\n"

        # 购买建议
        report += "## 🎯 购买建议\n\n"
        report += self._generate_recommendations(products, review_analysis, price_monitoring)

        report += "\n---\n\n"
        report += f"*报告由 Multi-Agent 购物调研系统自动生成*\n"

        return report

    def _generate_recommendations(
        self,
        products: List[Product],
        review_analysis: Dict[str, Any],
        price_monitoring: Dict[str, Any]
    ) -> str:
        """生成购买建议"""
        recommendations = ""

        # 1. 最优选择
        best_deal = price_monitoring.get('best_deal')
        if best_deal:
            recommendations += f"### ✅ 综合推荐\n\n"
            recommendations += f"**{best_deal['title']}** ({best_deal['platform']})\n"
            recommendations += f"- 价格: ¥{best_deal['price']}\n"
            recommendations += f"- 性价比得分最高\n\n"

        # 2. 风险提示
        high_risk_products = [
            analysis for analysis in review_analysis.values()
            if analysis['risk_level'] == 'high'
        ]

        if high_risk_products:
            recommendations += f"### ⚠️ 风险提示\n\n"
            for analysis in high_risk_products:
                recommendations += f"- **{analysis['product_title']}**: 检测到较多负面评价，建议谨慎购买\n"
            recommendations += "\n"

        # 3. 平台选择建议
        recommendations += "### 📱 平台选择建议\n\n"
        recommendations += "- **闲鱼**: 价格更低，但需注意商品真伪和成色\n"
        recommendations += "- **淘宝/天猫**: 官方旗舰店更有保障，售后完善\n"
        recommendations += "- **京东**: 配送快速，自营商品质量可靠\n\n"

        return recommendations

    def _build_report_slug(self, query: str) -> str:
        cleaned = re.sub(r"[^\w\u4e00-\u9fff]+", "_", str(query or "").strip().lower())
        cleaned = re.sub(r"_+", "_", cleaned).strip("_")
        cleaned = cleaned[:48] or "query"
        return f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{cleaned}"


if __name__ == "__main__":
    # 测试代码
    from agents.scraper_agent.agent import ScraperAgent
    from agents.review_analyzer_agent.agent import ReviewAnalyzerAgent
    from agents.price_monitor_agent.agent import PriceMonitorAgent

    # 1. 抓取数据
    scraper = ScraperAgent()
    products = scraper.fetch_products("iPhone 15 Pro", platforms=['xianyu', 'taobao'])

    # 2. 分析评价
    analyzer = ReviewAnalyzerAgent()
    review_analysis = analyzer.analyze_reviews(products)

    # 3. 监控价格
    monitor = PriceMonitorAgent()
    price_monitoring = monitor.monitor_prices(products)

    # 4. 生成报告
    generator = ReportGeneratorAgent()
    report_artifacts = generator.generate_report(
        products, review_analysis, price_monitoring, "iPhone 15 Pro"
    )

    print(f"\n✅ 报告已生成: {report_artifacts.get('report_path')}")
