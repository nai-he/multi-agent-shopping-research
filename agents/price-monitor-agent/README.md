# PriceMonitorAgent

`PriceMonitorAgent` is responsible for turning raw product samples into price comparison signals, value ranking, and anomaly alerts.

## Role In The System

- Persist product price snapshots into SQLite
- Compare price ranges across returned samples
- Compute a simple value score for ranking
- Flag unusually low or high prices

## Inputs

- A list of normalized `Product` objects from `ScraperAgent`

## Outputs

- `price_comparison`
  - min price
  - max price
  - average price
  - price range
  - cheapest product
  - most expensive product
- `value_ranking`
- `price_alerts`
- `best_deal`

## Value Score

The current heuristic is intentionally lightweight and explainable:

```text
value_score = (seller_rating * positive_rate * (1 + sales_factor * 0.1)) / price
sales_factor = log10(sales + 1)
```

This favors products with:

- lower price
- better seller rating
- higher positive review rate
- non-zero sales signal

## Persistence

Historical price snapshots are stored in:

- [../../data/database/price_history.db](/E:/agentlearn/design/data/database/price_history.db)

Table shape:

```sql
CREATE TABLE IF NOT EXISTS price_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    title TEXT,
    price REAL NOT NULL,
    seller_rating REAL,
    timestamp TEXT NOT NULL
);
```

## Important Files

- [agent.py](/E:/agentlearn/design/agents/price-monitor-agent/agent.py)

## How To Use

```python
from agent import PriceMonitorAgent

monitor = PriceMonitorAgent()
result = monitor.monitor_prices(products)
```

## Why This Matters In A Portfolio

This agent shows that the project is not just scraping pages. It adds a second stage that:

- persists data
- computes derived metrics
- produces reusable signals for ranking and reporting

That makes the system look more like an analysis pipeline than a crawler demo.

## Current Limits

- The value score is heuristic, not learned
- Cross-platform product equivalence is approximate
- Historical price tracking is append-only and does not yet deduplicate the same listing across runs
