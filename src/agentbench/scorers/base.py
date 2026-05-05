from __future__ import annotations

from typing import Protocol

from agentbench.core.result import AgentRunResult, ScoreResult
from agentbench.core.task import TaskSpec


class Scorer(Protocol):
    """评分器需要实现的最小协议。"""

    def score(self, task: TaskSpec, run: AgentRunResult) -> ScoreResult:
        """根据任务定义和 Agent 运行结果计算得分。"""
        ...
