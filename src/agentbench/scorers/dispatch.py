from __future__ import annotations

from agentbench.core.result import AgentRunResult, ScoreResult
from agentbench.core.task import TaskSpec
from agentbench.scorers.base import Scorer
from agentbench.scorers.hybrid import HybridScorer
from agentbench.scorers.judge import JudgeScorer
from agentbench.scorers.rules import RuleScorer


class DispatchScorer:
    """Dispatch scoring to the scorer required by each task's mode."""

    def __init__(
        self,
        rule_scorer: Scorer | None = None,
        judge_scorer: Scorer | None = None,
        hybrid_scorer: Scorer | None = None,
    ) -> None:
        self.rule_scorer = rule_scorer or RuleScorer()
        self.judge_scorer = judge_scorer or JudgeScorer()
        self.hybrid_scorer = hybrid_scorer or HybridScorer(judge_scorer=self.judge_scorer)

    def score(self, task: TaskSpec, run: AgentRunResult) -> ScoreResult:
        if task.scoring.mode == "rules":
            return self.rule_scorer.score(task, run)
        if task.scoring.mode == "judge":
            return self.judge_scorer.score(task, run)
        if task.scoring.mode == "hybrid":
            return self.hybrid_scorer.score(task, run)
        raise ValueError(f"unsupported scoring mode: {task.scoring.mode}")
