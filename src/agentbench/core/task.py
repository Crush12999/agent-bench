from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml


WorkspacePolicy = Literal["all", "failed", "none"]
ScoringMode = Literal["rules", "judge", "hybrid"]
JudgeMode = Literal["agent", "api"]


@dataclass(frozen=True)
class SeedFile:
    source: str
    dest: str


@dataclass(frozen=True)
class RuleSpec:
    id: str
    type: str
    points: float
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ScoringSpec:
    mode: ScoringMode
    rules: list[RuleSpec] = field(default_factory=list)
    judge_rubric: str | None = None
    weights: dict[str, float] | None = None


@dataclass(frozen=True)
class TaskSpec:
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
    mode: JudgeMode = "agent"
    model: str | None = None


@dataclass(frozen=True)
class RunConfig:
    adapter: str
    model: str
    trials: int = 1
    parallelism: int = 1
    output_dir: str = "runs"
    workspace_policy: WorkspacePolicy = "failed"
    adapter_config: dict[str, Any] = field(default_factory=dict)
    judge: JudgeConfig | None = None


def load_task_spec(path: str | Path) -> TaskSpec:
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


def load_run_config(path: str | Path) -> RunConfig:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    run = raw.get("run") or raw
    judge_raw = run.get("judge")
    judge = JudgeConfig(mode=judge_raw.get("mode", "agent"), model=judge_raw.get("model")) if judge_raw else None
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
