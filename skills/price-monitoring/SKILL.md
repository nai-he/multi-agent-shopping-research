---
name: price-monitoring
description: Use when products are scraped and need price comparison, before generating the final report. Computes price statistics, identifies best value deals, detects price anomalies, and generates price alerts. Uses AI to generate contextual buying advice based on price patterns.
metadata:
  agent: PriceMonitorAgent
  priority: 4
  requires: product-scraping
---

# Price Monitoring Skill

## Purpose

Analyze prices across platforms and products to find the best deals, identify outliers, and generate actionable buying advice.

## When to Trigger

- Products have been scraped with valid prices
- User wants to compare prices across platforms
- Need to find best value (性价比) products

## Workflow

### Step 1: Price Normalization

- Strip currency symbols and convert all prices to float
- Handle platform-specific pricing (e.g., JD includes tax, Xianyu is negotiable)
- Flag products with obviously wrong prices (<1 or >1,000,000)

### Step 2: Compute Statistics

Per platform and overall:
- **min_price**: Lowest price found
- **max_price**: Highest price found
- **avg_price**: Mean price
- **median_price**: Median (more robust than mean)
- **price_range**: max - min
- **price_stddev**: Standard deviation
- **quartiles**: Q1, Q2 (median), Q3 for box plot

### Step 3: Detect Anomalies

Flag products where:
- Price is < 50% of category average (possible scam/bait listing)
- Price is > 200% of category average (possible scalping)
- Price dropped significantly from historical data
- Price is "too good to be true" for the condition

### Step 4: Compute Value Scores

For each product:
```
value_score = (seller_rating_normalized * 0.3 + review_score_normalized * 0.3 + sales_factor * 0.2) / price_normalized * 100
```
Higher score = better value.

### Step 5: AI-Powered Price Analysis

Send price data to Claude for contextual analysis:

```
You are a shopping price analyst. Given these products and their prices:

[product price data]

Provide:
1. Is this a good time to buy this category?
2. Which platform has the best prices for this category?
3. Are there any suspiciously cheap listings that should be flagged?
4. What price should the user expect to pay for a good-quality item?
5. Any seasonal pricing patterns to be aware of?
6. Specific negotiation tips for this platform/category

Format as structured JSON.
```

### Step 6: Generate Price Alerts

Conditions that trigger alerts:
- **warning**: Price < 70% of average (possible too good to be true)
- **info**: Price < 85% of average (good deal)
- **warning**: Price > 130% of average (overpriced)
- **info**: Significant price drop detected from history

### Step 7: Build Value Ranking

Rank all products by value_score, annotating top 5 with:
- Why it's a good deal
- Any trade-offs (lower seller rating, fewer reviews)
- Platform-specific notes

## Output Format

```json
{
  "price_comparison": {
    "min_price": 0, "max_price": 0, "avg_price": 0,
    "median_price": 0, "price_range": 0
  },
  "platform_breakdown": {
    "xianyu": {"avg": 0, "count": 0, "min": 0, "max": 0}
  },
  "anomalies": [{"product": "...", "reason": "..."}],
  "price_alerts": [{"level": "warning|info", "product": "...", "message": "..."}],
  "value_ranking": [{"title": "...", "price": 0, "value_score": 0, "platform": "..."}],
  "best_deal": {"title": "...", "price": 0, "value_score": 0, "platform": "..."},
  "ai_analysis": {"buy_timing": "...", "expected_price": 0, "tips": ["..."]}
}
```

## Anti-Patterns

- Do NOT compute value scores without normalizing prices first
- Do NOT skip anomaly detection — it catches scams
- Do NOT recommend the absolute cheapest without checking seller quality
