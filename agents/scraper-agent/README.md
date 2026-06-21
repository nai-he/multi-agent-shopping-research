# ScraperAgent

`ScraperAgent` is the data acquisition layer of the project. It converts a user query plus structured filters into platform-specific product samples from Xianyu, Taobao, JD, and Pinduoduo.

## Role In The System

- Accept normalized search intent from `MultiAgentCoordinator`
- Build a query plan for one or more marketplaces
- Execute scraping in `mock` or `real` mode
- Return normalized `Product` objects plus crawl diagnostics
- Persist crawl progress metadata for UI and debugging

## Inputs

- `query`: user search query
- `platforms`: selected platforms such as `xianyu`, `taobao`, `jd`, `pdd`
- `max_results_per_platform`: target sample count
- `location`: optional geographic filter
- `sort_order`: `none`, `price_asc`, or `price_desc`
- `search_keywords`: AI-expanded query candidates
- `category` / `sub_category`: optional intent labels
- `budget_min` / `budget_max`: optional price bounds

## Outputs

- A list of normalized `Product` objects
- Crawl metadata stored in `last_crawl_meta`
  - estimated total
  - progress text
  - per-platform diagnostics
  - login / risk-control signals
  - suggested next action

## Key Capabilities

### 1. Query Planning

- Expands a broad user request into a small set of search candidates
- Separates the ranking query from live crawl queries
- Supports category-aware and budget-aware query refinement

### 2. Dual Runtime Modes

- `mock` mode loads local fixture data for demos and regression checks
- `real` mode uses Playwright-based live scrapers for marketplace pages

### 3. Session Reuse

- Supports persistent browser profiles for manual login bootstrap
- Reuses `storage_state.json` in headless runs to avoid profile lock issues
- Falls back gracefully when Chrome profile startup is unavailable

### 4. Failure Diagnostics

- Distinguishes between:
  - no results
  - login required
  - anti-bot / risk-control triggered
  - platform-specific scraping failure
- Produces platform-level status messages for the web UI result page

## Important Files

- [agent.py](/E:/agentlearn/design/agents/scraper-agent/agent.py)
- [live_scrapers/marketplace_playwright.py](/E:/agentlearn/design/agents/scraper-agent/live_scrapers/marketplace_playwright.py)
- [live_scrapers/xianyu_playwright.py](/E:/agentlearn/design/agents/scraper-agent/live_scrapers/xianyu_playwright.py)
- [../../scripts/diagnose_marketplace.py](/E:/agentlearn/design/scripts/diagnose_marketplace.py)
- [../../scripts/bootstrap_marketplace_session.py](/E:/agentlearn/design/scripts/bootstrap_marketplace_session.py)

## How To Use

```python
from agent import ScraperAgent

agent = ScraperAgent()
products = agent.fetch_products(
    query="iPhone 15 Pro",
    platforms=["xianyu", "taobao"],
    max_results_per_platform=20,
    location="福建",
    sort_order="price_asc",
)
```

## CLI Diagnostics

```bash
python scripts/diagnose_marketplace.py --platform taobao --query "鞋子" --sample-count 10
python scripts/bootstrap_marketplace_session.py --platform taobao
```

## Engineering Notes

- Uses hyphenated agent folders because the project started as a directory-oriented multi-agent workspace rather than a standard Python package layout
- `MultiAgentCoordinator` loads agent classes through `importlib` to work with that structure
- Real scraping is the least stable part of the system because marketplace anti-bot behavior changes over time

## Current Limits

- Live scraping quality depends on platform volatility and login state
- Some platforms may return partial data or anti-bot responses even with session reuse
- For portfolio/demo use, `mock` mode and platform diagnostics are more reliable than claiming full production scraping coverage
