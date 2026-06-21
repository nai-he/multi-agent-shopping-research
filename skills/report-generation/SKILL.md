---
name: report-generation
description: Use when all analysis is complete and the user needs a final report, as the last step. Generates professional Markdown reports with embedded charts (price line chart, sentiment pie, seller radar, value ranking, platform boxplot), structured product tables, and AI-written executive summaries and buying recommendations.
metadata:
  agent: ReportGeneratorAgent
  priority: 5
  requires: review-analysis, price-monitoring
---

# Report Generation Skill

## Purpose

Synthesize all analysis results into a comprehensive, visually-rich shopping research report with AI-generated insights and professional charts.

## When to Trigger

- All analysis phases (review, price) are complete
- User requested a report download
- Need to present findings in a readable format

## Workflow

### Step 1: Gather All Data

Collect from previous skills:
- Products list (from product-scraping)
- Review analysis (from review-analysis)
- Price monitoring (from price-monitoring)
- Crawl metadata (estimated totals, progress)

### Step 2: Generate Charts

Create 5 standard charts:

1. **Price-Quantity Distribution Line Chart** (`price_comparison.png`)
   - X-axis: price buckets (auto-binned, 10-20 bins)
   - Left Y-axis: product count per bucket (blue line + fill)
   - Right Y-axis: cumulative percentage (red dashed line)
   - Above each point: count label
   - Title: "价格-数量分布折线图"

2. **Seller Reputation Radar** (`seller_radar.png`)
   - Polar chart comparing top 3 products
   - Axes: Rating, Ship Speed, Service, Positive Rate, Sales
   - Different color per product

3. **Sentiment Pie Chart** (`sentiment_pie.png`)
   - Positive (green) / Neutral (yellow) / Negative (red)
   - Percentage labels

4. **Value Ranking Bar Chart** (`value_ranking.png`)
   - Horizontal bars for top 5 products by value score
   - Score labels on bars

5. **Platform Box Plot** (`platform_boxplot.png`)
   - Price distribution per platform
   - Color-coded by platform

### Step 3: AI-Generated Executive Summary

Send structured data to Claude:

```
You are a shopping research analyst. Write a concise executive summary for this report:

Query: [user's search]
Products found: [count]
Platforms searched: [list]
Price range: [min]-[max]
Best deal: [product name] at ¥[price] on [platform]
Key findings: [bullet points from analysis]

Write 3 sections:
1. Market Overview (2-3 sentences on pricing landscape)
2. Top Recommendation (which product to buy and why)
3. Risks to Watch (key concerns from review analysis)

Write in professional but accessible Chinese. Be specific with numbers.
```

### Step 4: Build Markdown Report

Structure:
```markdown
# 购物调研报告：[query]

## 价格对比分析
- Price overview table
- Price distribution chart
- Product detail table (all products)

## 性价比分析
- Value ranking chart
- Best deal highlight
- Price alerts

## 评价分析
- Sentiment pie chart
- Per-product review analysis
- Risk assessments

## 卖家信誉对比
- Seller radar chart

## 购买建议
- AI-generated recommendations
- Platform comparison advice
- Risk warnings
```

### Step 5: Save and Return

- Save report to `reports/shopping_report_{timestamp}.md`
- Save charts to `reports/charts/*.png`
- Return file path for download

## Chart Technical Specs

- DPI: 150
- Font: SimHei / Microsoft YaHei for Chinese support
- Size: 10-12 inches width, 6-8 inches height
- Format: PNG with tight bounding box
- Backend: matplotlib Agg (non-interactive)

## Product Table Format

| 平台 | 商品标题 | 价格 | 卖家 | 信誉 | 销量 | 好评率 |
|------|---------|------|------|------|------|--------|
| 闲鱼 | iPhone 15 Pro... | ¥6299 | 张三 | 4.8⭐ | 156 | 96.5% |

ALL products must be listed, not just top N.

## Anti-Patterns

- Do NOT generate charts without data validation first
- Do NOT truncate product tables to top 30
- Do NOT use AI summary without including actual data numbers
- Do NOT skip chart generation — visual data is critical for decision making
