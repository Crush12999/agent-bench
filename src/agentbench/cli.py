from __future__ import annotations

import argparse
from pathlib import Path

from agentbench.adapters.fake import FakeAgentLoop
from agentbench.adapters.openclaw import OpenClawAgentLoop
from agentbench.core.runner import Runner
from agentbench.core.task import RunConfig, TaskSpec, load_run_config, load_task_spec
from agentbench.scorers.hybrid import HybridScorer
from agentbench.scorers.rules import RuleScorer


def load_tasks_from_path(path: str | Path) -> list[TaskSpec]:
    base = Path(path)
    files = sorted(base.glob("*.yaml")) if base.is_dir() else [base]
    return [load_task_spec(file) for file in files]


def select_scorer(tasks: list[TaskSpec]):
    modes = {task.scoring.mode for task in tasks}
    if "hybrid" in modes:
        return HybridScorer()
    if "judge" in modes:
        return HybridScorer(rule_scorer=RuleScorer())
    return RuleScorer()


def build_agent_loop(config: RunConfig):
    if config.adapter == "fake":
        return FakeAgentLoop()
    if config.adapter == "openclaw":
        return OpenClawAgentLoop(
            openclaw_binary=str(config.adapter_config.get("openclaw_binary", "openclaw")),
            session_artifact_timeout_seconds=int(config.adapter_config.get("session_artifact_timeout_seconds", 15)),
        )
    raise ValueError(f"unsupported adapter: {config.adapter}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agentbench")
    sub = parser.add_subparsers(dest="command", required=True)
    run_parser = sub.add_parser("run")
    run_parser.add_argument("--config", required=True)
    run_parser.add_argument("tasks")
    args = parser.parse_args(argv)

    if args.command == "run":
        config = load_run_config(args.config)
        tasks = load_tasks_from_path(args.tasks)
        runner = Runner(config=config, agent_loop=build_agent_loop(config), scorer=select_scorer(tasks))
        result = runner.run(tasks)
        print(result["run_dir"])
        return 0
    return 1
