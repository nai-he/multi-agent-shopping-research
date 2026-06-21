---
name: review-analysis
description: Use when products are scraped and need quality assessment, before making recommendations. Analyzes product reviews for sentiment, risk level, fake review detection, and key issues extraction. Uses Claude API for nuanced sentiment analysis instead of keyword matching.
metadata:
  agent: ReviewAnalyzerAgent
  priority: 3
  requires: product-scraping
---

# Review Analysis Skill

## Purpose

Analyze product reviews using AI to assess product quality, detect risks, and extract actionable insights. Replaces simple keyword matching with LLM-powered sentiment understanding.

## When to Trigger

- Products have been scraped with reviews attached
- User wants to know product quality/reliability
- Need risk assessment before making purchase recommendations

## Workflow

### Step 1: Preprocess Reviews

For each product with reviews:
- Filter out empty/spam reviews
- Sort by recency and helpfulness
- Sample reviews if count exceeds 50 (take newest + most helpful)

### Step 2: AI Sentiment Analysis

Per product, send reviews to Claude with this analysis prompt:

```
Analyze these product reviews. For each review, classify:
- sentiment: positive/neutral/negative
- confidence: 0-1
- topics_mentioned: [list]
- is_fake_review: true/false (look for templated language, excessive praise, no specifics)

Then provide:
- overall_sentiment_distribution: {positive: N, neutral: N, negative: N}
- key_positive_points: [top 3 things praised]
- key_negative_points: [top 3 things complained about]
- risk_level: low/medium/high
- risk_reasons: [specific concerns]
- fake_review_estimate: percentage likely fake
- recommended: true/false
- recommendation_reason: one sentence
```

### Step 3: Aggregate Cross-Product Insights

Across all products:
- Common praise themes
- Common complaint themes  
- Platform-specific quality patterns (e.g., "Xianyu sellers tend to overstate condition")
- Category-specific risks (e.g., "Used phones: battery health is the #1 concern")

### Step 4: Compute Risk Levels

- **low risk**: >80% positive, no fake review pattern, seller has good reputation
- **medium risk**: 60-80% positive, some concerns, mixed reviews
- **high risk**: <60% positive, fake review patterns detected, seller has issues

### Step 5: Extract Key Issues

Top issues that should influence the buying decision:
- Quality concerns
- Authenticity concerns
- Seller reliability
- Shipping/delivery issues
- Price-to-value mismatch

## Fake Review Detection Patterns

LLM should look for:
1. Template language ("质量很好，很满意" repeated across reviews)
2. No specific details about product usage
3. All 5-star with no criticism whatsoever
4. Review posted within seconds of purchase
5. Similar review text across different products from same seller
6. Review mentions unrelated products
7. Reviewer account has only one review

## Output Format

```json
{
  "product_id": "...",
  "sentiment_summary": {"positive": N, "neutral": N, "negative": N},
  "key_positive_points": ["...", "..."],
  "key_negative_points": ["...", "..."],
  "risk_level": "low|medium|high",
  "risk_reasons": ["..."],
  "fake_review_estimate": 0.0-1.0,
  "recommended": true/false,
  "recommendation_reason": "...",
  "review_count_analyzed": N,
  "confidence": 0.0-1.0
}
```

## Anti-Patterns

- Do NOT skip AI analysis and fall back to keyword matching
- Do NOT analyze without checking for empty reviews
- Do NOT recommend products with high fake review estimates
