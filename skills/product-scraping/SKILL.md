---
name: product-scraping
description: Use when the intent is parsed and search keywords are ready, before any analysis. Scrapes multiple Chinese e-commerce platforms (Xianyu/Goofish, Taobao, JD, PDD) with AI-expanded keywords, automatic deduplication, and relevance filtering. Handles regional filtering (province/city mapping), platform-specific rate limiting, and anti-blocking strategies.
metadata:
  agent: ScraperAgent
  priority: 2
  requires: intent-parsing
---

# Product Scraping Skill

## Purpose

Execute multi-platform product searches using AI-generated keyword variations. Aggregate, deduplicate, and filter results into clean Product objects ready for analysis.

## When to Trigger

- `intent-parsing` skill has completed and produced `search_keywords`
- User wants to search specific platforms for specific products
- Need to estimate total available products before full scrape

## Workflow

### Step 1: Prepare Search Parameters

From the intent result:
- Primary query = user's original input
- Search keywords = `intent.search_keywords` (AI-expanded list)
- Platforms = user-selected (xianyu/taobao/jd/pdd)
- Location = user-selected province/city
- Sort order = user preference (none/price_asc/price_desc)

### Step 2: Estimate Totals (Optional but Recommended)

Before full scrape, call the estimate endpoint to get total result counts. This helps set realistic expectations and sample counts.

### Step 3: Iterative Search

For each platform + keyword combination:
1. Map city names to province names for Goofish API compatibility
2. Launch Playwright/Selenium browser with persistent profile
3. Search with keyword, location, sort parameters
4. Collect raw product data (title, price, sales, seller, images, url)
5. Track progress via callback

### Step 4: Deduplicate Results

Across all keyword variations:
- Deduplicate by product_id
- Deduplicate by URL match
- Keep the entry with most complete data

### Step 5: Relevance Filtering

Filter out:
- Clearly wrong category (查手机结果里有手机壳)
- Price anomalies (<10% or >500% of average for category)
- Obvious spam/ads
- Sold/expired listings (on Xianyu)

### Step 6: Convert to Product Objects

Standardize all platform-specific data into the shared Product model:
- Normalize price format (remove currency symbols, convert to float)
- Extract seller reputation info
- Map platform-specific statuses

### Step 7: Sort and Return

Apply user's sort preference:
- price_asc: cheapest first
- price_desc: most expensive first
- none: relevance order from platform

## Platform-Specific Notes

### Xianyu (闲鱼/Goofish)
- Uses Goofish API with province-level location filtering
- City→Province mapping required (厦门→福建)
- May trigger anti-bot protection — use persistent browser profiles
- Headless mode works but is more likely to be blocked

### Taobao (淘宝)
- Rate limiting: ~50 requests/minute
- Requires logged-in session for full results

### JD (京东)
- API-based scraping preferred over browser
- Price includes tax by default

### PDD (拼多多)
- Heavy anti-bot protection
- Browser-based scraping with long delays required

## Error Handling

- XianyuScrapeBlocked: Switch to mock data or prompt user to log in
- Platform timeout: Skip platform, continue with others
- All platforms fail: Return meaningful error with suggestions

## Anti-Patterns

- Do NOT scrape without location filtering if user specified a location
- Do NOT return raw platform data without Product model conversion
- Do NOT skip deduplication step
