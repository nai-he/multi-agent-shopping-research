# ReportGeneratorAgent

`ReportGeneratorAgent` converts structured analysis results into portfolio-friendly deliverables: a Markdown report and several charts.

## Role In The System

- Generate report artifacts from upstream agent outputs
- Save chart images under `reports/charts/`
- Save Markdown reports under `reports/`

## Inputs

- `products`
- `review_analysis`
- `price_monitoring`
- `query`

## Outputs

- `report_path`
- `charts`

Typical chart outputs include:

- price comparison
- seller radar
- sentiment pie
- value ranking
- platform boxplot

## Important Files

- [agent.py](/E:/agentlearn/design/agents/report-generator-agent/agent.py)
- [../../reports](/E:/agentlearn/design/reports)

## How To Use

```python
from agent import ReportGeneratorAgent

generator = ReportGeneratorAgent()
artifacts = generator.generate_report(
    products=products,
    review_analysis=review_analysis,
    price_monitoring=price_monitoring,
    query="iPhone 15 Pro",
)
```

## Why This Matters In A Portfolio

This is the part interviewers can see immediately. It turns a backend pipeline into something demonstrable:

- human-readable report output
- chart assets
- reusable artifacts for the web UI

It helps position the project as an end-to-end analysis system instead of a collection of scripts.

## Current Limits

- The report is template-driven rather than LLM-authored
- Chart design is functional but still conservative
- There is no export to PDF or slide deck yet
