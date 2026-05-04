from __future__ import annotations

from typing import Protocol

from agentbench.core.result import AgentRunResult, ScoreResult
from agentbench.core.task import TaskSpec


class Scorer(Protocol):
    def score(self, task: TaskSpec, run: AgentRunResult) -> ScoreResult:
        ...
