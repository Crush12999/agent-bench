from __future__ import annotations

import argparse
from pathlib import Path

from agentbench.adapters.fake import FakeAgentLoop
from agentbench.adapters.openclaw import OpenClawAgentLoop
from agentbench.core.runner import Runner
from agentbench.core.task import RunConfig, TaskSpec, load_run_config, load_task_spec
from agentbench.env import load_dotenv
from agentbench.scorers.hybrid import HybridScorer
from agentbench.scorers.judge import JudgeScorer
from agentbench.scorers.rules import RuleScorer


def load_tasks_from_path(path: str | Path) -> list[TaskSpec]:
    """从单个 YAML 文件或目录批量加载任务。"""
    base = Path(path)
    files = sorted(base.glob("*.yaml")) if base.is_dir() else [base]
    return [load_task_spec(file) for file in files]


def select_scorer(config: RunConfig, tasks: list[TaskSpec]):
    """根据任务中声明的 scoring mode 选择评分器。"""
    modes = {task.scoring.mode for task in tasks}
    if "hybrid" in modes:
        return HybridScorer(judge_scorer=JudgeScorer(config.judge))
    if "judge" in modes:
        return JudgeScorer(config.judge)
    return RuleScorer()


def build_agent_loop(config: RunConfig):
    """根据运行配置创建对应的 Agent 适配器。"""
    if config.adapter == "fake":
        return FakeAgentLoop()
    if config.adapter == "openclaw":
        return OpenClawAgentLoop(
            openclaw_binary=str(config.adapter_config.get("openclaw_binary", "openclaw")),
            model=config.model,
            state_dir=Path(str(config.adapter_config["state_dir"])) if config.adapter_config.get("state_dir") else None,
            session_artifact_timeout_seconds=int(config.adapter_config.get("session_artifact_timeout_seconds", 15)),
        )
    raise ValueError(f"unsupported adapter: {config.adapter}")


def main(argv: list[str] | None = None) -> int:
    """命令行入口。"""
    parser = argparse.ArgumentParser(prog="agentbench")
    sub = parser.add_subparsers(dest="command", required=True)
    run_parser = sub.add_parser("run")
    run_parser.add_argument("--config", required=True)
    run_parser.add_argument("tasks")
    args = parser.parse_args(argv)

    if args.command == "run":
        load_dotenv(Path.cwd() / ".env")
        config = load_run_config(args.config)
        tasks = load_tasks_from_path(args.tasks)
        runner = Runner(config=config, agent_loop=build_agent_loop(config), scorer=select_scorer(config, tasks))
        result = runner.run(tasks)
        print(result["run_dir"])
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
