from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from agentbench.core.trace import Trace


RunStatus = Literal["success", "timeout", "error", "preflight_failed"]
ScoreStatus = Literal["scored", "scoring_error", "skipped"]


@dataclass(frozen=True)
class AgentRunResult:
    task_id: str
    trial_id: int
    status: RunStatus
    started_at: str
    finished_at: str
    duration_seconds: float
    workspace_path: str
    log_dir: str
    stdout_path: str
    stderr_path: str
    trace_path: str
    adapter_log_path: str
    trace: Trace = field(default_factory=Trace)
    usage: dict[str, Any] | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "trial_id": self.trial_id,
            "status": self.status,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_seconds": self.duration_seconds,
            "workspace_path": self.workspace_path,
            "log_dir": self.log_dir,
            "stdout_path": self.stdout_path,
            "stderr_path": self.stderr_path,
            "trace_path": self.trace_path,
            "adapter_log_path": self.adapter_log_path,
            "trace": self.trace.to_dict(),
            "usage": self.usage,
            "error": self.error,
        }


@dataclass(frozen=True)
class CheckResult:
    id: str
    score: float
    points: float
    passed: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "score": self.score,
            "points": self.points,
            "passed": self.passed,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class ScoreResult:
    task_id: str
    trial_id: int
    status: ScoreStatus
    score: float
    passed: bool
    breakdown: list[CheckResult] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "trial_id": self.trial_id,
            "status": self.status,
            "score": self.score,
            "passed": self.passed,
            "breakdown": [item.to_dict() for item in self.breakdown],
            "notes": self.notes,
        }
