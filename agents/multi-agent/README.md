# MultiAgentCoordinator

`MultiAgentCoordinator` is the orchestration layer of the system. It wires together the four functional agents into a single research pipeline.

## Pipeline

1. `ScraperAgent`
2. `ReviewAnalyzerAgent`
3. `PriceMonitorAgent`
4. `ReportGeneratorAgent`

The current implementation runs review analysis and price monitoring in parallel after scraping completes.

## Responsibilities

- initialize all sub-agents
- load workflow configuration
- execute the end-to-end flow
- collect timing and status
- return a result bundle for CLI and Web consumers

## Execution Flow

```text
User Query
  -> Coordinator
  -> ScraperAgent
  -> ReviewAnalyzerAgent + PriceMonitorAgent (parallel)
  -> ReportGeneratorAgent
  -> Report path + charts + structured results
```

## Important Files

- [coordinator.py](/E:/agentlearn/design/agents/multi-agent/coordinator.py)
- [main.py](/E:/agentlearn/design/agents/multi-agent/main.py)
- [../../config/workflow_config.json](/E:/agentlearn/design/config/workflow_config.json)

## CLI Entry

```bash
python agents/multi-agent/main.py --query "iPhone 15 Pro" --platforms xianyu taobao
```

## Why This Matters In A Portfolio

This file is the clearest proof that the project is architected as a multi-stage system rather than a single script. It shows:

- modular decomposition
- orchestration
- result passing between stages
- partial parallelism

## Current Limits

- Agent communication is local direct function invocation
- There is no queue, workflow engine, or distributed execution layer
- The architecture is best described as a local multi-agent prototype rather than a production orchestration platform
