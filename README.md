# AgentBench

AgentBench is a minimal OpenClaw-first agent evaluation framework with a runtime adapter boundary.

Version 1 supports OpenClaw execution, isolated trial workspaces, JSON reports, rule scoring, judge scoring, hybrid scoring, and reliability metrics.

## Local fake run

```bash
agentbench run --config examples/run.fake.yaml examples/tasks
```

The command writes a run directory under `runs/` containing:

- `run.json`
- `trials.jsonl`
- `logs/{task}/trial-{n}/result.json`
- isolated workspaces according to `workspace_policy`
