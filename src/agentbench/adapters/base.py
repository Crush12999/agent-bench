from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from agentbench.core.result import AgentRunResult
from agentbench.core.task import RunConfig, TaskSpec


@dataclass(frozen=True)
class PreflightResult:
    ok: bool
    message: str = ""


class AgentLoop(Protocol):
    def preflight(self, config: RunConfig) -> PreflightResult:
        ...

    def run(
        self,
        task: TaskSpec,
        trial_id: int,
        workspace: Path,
        log_dir: Path,
        timeout_seconds: int,
    ) -> AgentRunResult:
        ...
