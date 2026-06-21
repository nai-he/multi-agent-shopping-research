# ReviewAnalyzerAgent

`ReviewAnalyzerAgent` analyzes review-level signals for the returned product set. It is designed as a lightweight post-processing stage rather than a full NLP research component.

## Role In The System

- Aggregate review sentiment
- Extract negative issue keywords
- Detect suspicious fake-review patterns
- Estimate a simple risk level per product

## Inputs

- A list of `Product` objects
- Each product may contain zero or more `Review` objects

## Outputs

Per product, the agent returns:

- sentiment summary
- negative keywords
- fake review detected or not
- risk level
- key issues
- positive rate

## Current Analysis Strategy

### Sentiment

- `rating >= 4.5` -> positive
- `rating >= 3.0` -> neutral
- otherwise -> negative

### Issue Extraction

- Matches review text against categorized negative keyword dictionaries
- Groups issues such as quality, description mismatch, service, logistics, and severe problems

### Fake Review Detection

- Looks for suspicious phrase patterns in review text
- Marks a product as suspicious when the ratio crosses a simple threshold

### Risk Estimation

Combines:

- negative review ratio
- presence of severe issue keywords
- fake-review suspicion
- low positive rate

## Important Files

- [agent.py](/E:/agentlearn/design/agents/review-analyzer-agent/agent.py)
- [../../shared/constants/keywords.py](/E:/agentlearn/design/shared/constants/keywords.py)

## How To Use

```python
from agent import ReviewAnalyzerAgent

analyzer = ReviewAnalyzerAgent()
review_result = analyzer.analyze_reviews(products)
```

## Why This Matters In A Portfolio

This agent demonstrates a second independent analysis axis beyond price:

- text classification
- rule-based issue mining
- risk scoring

Even though the implementation is simple, it helps show system decomposition and post-scrape enrichment.

## Current Limits

- Review quality depends on the scraped platform data
- Sentiment is rule-based, not model-based
- Fake-review detection is heuristic and should be presented as a signal, not a certainty
