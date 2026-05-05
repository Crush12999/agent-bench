from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml


WorkspacePolicy = Literal["all", "failed", "none"]
ScoringMode = Literal["rules", "judge", "hybrid"]
JudgeProvider = Literal["openai", "anthropic"]


@dataclass(frozen=True)
class SeedFile:
    """任务开始前需要复制进工作区的种子文件。"""

    source: str
    dest: str


@dataclass(frozen=True)
class RuleSpec:
    """单条规则评分项的配置。"""

    id: str
    type: str
    points: float
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ScoringSpec:
    """任务的评分方式和评分参数。"""

    mode: ScoringMode
    rules: list[RuleSpec] = field(default_factory=list)
    judge_rubric: str | None = None
    weights: dict[str, float] | None = None


@dataclass(frozen=True)
class TaskSpec:
    """从任务 YAML 加载后的标准任务描述。"""

    id: str
    name: str
    prompt: str
    timeout_seconds: int
    pass_threshold: float = 0.6
    seed_files: list[SeedFile] = field(default_factory=list)
    scoring: ScoringSpec = field(default_factory=lambda: ScoringSpec(mode="rules"))
    metadata: dict[str, str] = field(default_factory=dict)
    source_path: Path | None = None


@dataclass(frozen=True)
class JudgeConfig:
    """Judge 评分器的运行配置。"""

    provider: JudgeProvider
    model: str
    base_url: str
    api_key_env: str
    temperature: float = 0.0
    timeout_seconds: int = 60
    max_tokens: int = 512
    max_context_chars: int = 20000
    max_tool_result_chars: int = 1000
    max_workspace_file_chars: int = 3000
    max_retries: int = 2
    retry_backoff_seconds: float = 1.0


@dataclass(frozen=True)
class RunConfig:
    """一次评测运行的全局配置。"""

    adapter: str
    model: str
    trials: int = 1
    parallelism: int = 1
    output_dir: str = "runs"
    workspace_policy: WorkspacePolicy = "failed"
    adapter_config: dict[str, Any] = field(default_factory=dict)
    judge: JudgeConfig | None = None


def load_task_spec(path: str | Path) -> TaskSpec:
    """从任务 YAML 文件加载并规范化任务配置。"""
    task_path = Path(path)
    raw = yaml.safe_load(task_path.read_text(encoding="utf-8")) or {}
    scoring_raw = raw.get("scoring") or {}
    rules = [
        RuleSpec(
            id=str(item["id"]),
            type=str(item["type"]),
            points=float(item.get("points", 1.0)),
            params=dict(item.get("params") or {}),
        )
        for item in scoring_raw.get("rules", [])
    ]
    scoring = ScoringSpec(
        mode=scoring_raw.get("mode", "rules"),
        rules=rules,
        judge_rubric=scoring_raw.get("judge_rubric"),
        weights=dict(scoring_raw["weights"]) if scoring_raw.get("weights") else None,
    )
    return TaskSpec(
        id=str(raw["id"]),
        name=str(raw.get("name", raw["id"])),
        prompt=str(raw.get("prompt", "")).strip(),
        timeout_seconds=int(raw.get("timeout_seconds", 180)),
        pass_threshold=float(raw.get("pass_threshold", 0.6)),
        seed_files=[
            SeedFile(source=str(item["source"]), dest=str(item["dest"]))
            for item in raw.get("seed_files", [])
        ],
        scoring=scoring,
        metadata={str(k): str(v) for k, v in dict(raw.get("metadata") or {}).items()},
        source_path=task_path,
    )


def _load_judge_config(raw: dict[str, Any] | None) -> JudgeConfig | None:
    if raw is None:
        return None

    provider = str(raw["provider"])
    default_base_urls = {
        "openai": "https://api.openai.com/v1",
        "anthropic": "https://api.anthropic.com",
    }
    default_api_key_envs = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
    }
    return JudgeConfig(
        provider=provider,
        model=str(raw["model"]),
        base_url=str(raw.get("base_url", default_base_urls.get(provider, ""))),
        api_key_env=str(raw.get("api_key_env", default_api_key_envs.get(provider, ""))),
        temperature=float(raw.get("temperature", 0.0)),
        timeout_seconds=int(raw.get("timeout_seconds", 60)),
        max_tokens=int(raw.get("max_tokens", 512)),
        max_context_chars=int(raw.get("max_context_chars", 20000)),
        max_tool_result_chars=int(raw.get("max_tool_result_chars", 1000)),
        max_workspace_file_chars=int(raw.get("max_workspace_file_chars", 3000)),
        max_retries=int(raw.get("max_retries", 2)),
        retry_backoff_seconds=float(raw.get("retry_backoff_seconds", 1.0)),
    )


def load_run_config(path: str | Path) -> RunConfig:
    """从运行配置 YAML 文件加载并规范化运行配置。"""
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    run = raw.get("run") or raw
    judge = _load_judge_config(run.get("judge"))
    return RunConfig(
        adapter=str(run["adapter"]),
        model=str(run["model"]),
        trials=int(run.get("trials", 1)),
        parallelism=int(run.get("parallelism", 1)),
        output_dir=str(run.get("output_dir", "runs")),
        workspace_policy=run.get("workspace_policy", "failed"),
        adapter_config=dict(run.get("adapter_config") or {}),
        judge=judge,
    )
