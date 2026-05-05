from __future__ import annotations

from agentbench.core.result import AgentRunResult, ScoreResult
from agentbench.core.task import TaskSpec


class JudgeScorer:
    """Judge 评分器占位实现。"""

    def score(self, task: TaskSpec, run: AgentRunResult) -> ScoreResult:
        """返回 skipped，避免在未配置 Judge 执行器时误报已评分。"""
        if not task.scoring.judge_rubric:
            return ScoreResult(
                task_id=task.id,
                trial_id=run.trial_id,
                status="skipped",
                score=0.0,
                passed=False,
                notes="judge_rubric missing",
            )
        return ScoreResult(
            task_id=task.id,
            trial_id=run.trial_id,
            status="skipped",
            score=0.0,
            passed=False,
            notes="judge execution is not configured",
        )
