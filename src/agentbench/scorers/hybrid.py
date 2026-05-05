from __future__ import annotations

from agentbench.core.result import AgentRunResult, ScoreResult
from agentbench.core.task import TaskSpec
from agentbench.scorers.base import Scorer
from agentbench.scorers.judge import JudgeScorer
from agentbench.scorers.rules import RuleScorer


class HybridScorer:
    """组合规则评分和 Judge 评分的混合评分器。"""

    def __init__(self, rule_scorer: Scorer | None = None, judge_scorer: Scorer | None = None) -> None:
        """允许测试注入替代评分器，默认使用内置规则和 Judge 评分器。"""
        self.rule_scorer = rule_scorer or RuleScorer()
        self.judge_scorer = judge_scorer or JudgeScorer()

    def score(self, task: TaskSpec, run: AgentRunResult) -> ScoreResult:
        """按任务配置的权重合并规则分和 Judge 分。"""
        rule_result = self.rule_scorer.score(task, run)
        judge_result = self.judge_scorer.score(task, run)
        weights = task.scoring.weights or {"rules": 0.7, "judge": 0.3}
        rule_weight = float(weights.get("rules", 0.7))
        judge_weight = float(weights.get("judge", 0.3))
        total_weight = rule_weight + judge_weight
        score = 0.0 if total_weight <= 0 else (rule_result.score * rule_weight + judge_result.score * judge_weight) / total_weight
        score = round(score, 4)
        return ScoreResult(
            task_id=task.id,
            trial_id=run.trial_id,
            status="scored",
            score=score,
            passed=score >= task.pass_threshold,
            breakdown=[*rule_result.breakdown, *judge_result.breakdown],
            notes="hybrid score",
        )
