# Agents Overview

This directory contains the project's multi-agent pipeline.

## Architecture

- `multi-agent/`: orchestration entrypoint and coordinator
- `scraper-agent/`: marketplace acquisition and crawl diagnostics
- `review-analyzer-agent/`: review-level issue and sentiment analysis
- `price-monitor-agent/`: price comparison, ranking, and alerts
- `report-generator-agent/`: Markdown report and chart generation

## Why The Layout Looks Like This

The folders use hyphenated names because the project was organized first as a human-readable workspace and demo project, not as a polished Python package. To keep that layout while remaining runnable, the coordinator loads agent classes dynamically through `importlib`.

That is not the cleanest Python packaging style, but it is a reasonable prototype tradeoff and easy to explain in an interview.

## Recommended Portfolio Framing

When presenting this project, describe it as:

> A Python-based multi-agent shopping research system that transforms natural-language shopping intent into multi-platform product sampling, review and price analysis, and downloadable reports.

That framing is stronger than calling it just a crawler or just a Flask app.

## Suggested Talking Points

- why the system is split into agents
- which stages are deterministic vs heuristic
- what changed when real scraping replaced mock data
- how failure diagnostics were added for login and anti-bot cases
- what would be refactored next if this became a production system
