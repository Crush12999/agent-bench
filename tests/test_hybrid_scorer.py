from pathlib import Path

from agentbench.core.result import AgentRunResult, ScoreResult
from agentbench.core.task import RuleSpec, ScoringSpec, TaskSpec
from agentbench.core.trace import Trace
from agentbench.scorers.hybrid import HybridScorer
from agentbench.scorers.rules import RuleScorer


class FixedJudge:
    def score(self, task, run):
        return ScoreResult(
            task_id=task.id,
            trial_id=run.trial_id,
            status="scored",
            score=0.5,
            passed=False,
            notes="fixed",
        )


def test_hybrid_combines_rule_and_judge_scores(tmp_path: Path):
    (tmp_path / "summary.md").write_text("ok", encoding="utf-8")
    task = TaskSpec(
        id="summary",
        name="Summary",
        prompt="p",
        timeout_seconds=1,
        scoring=ScoringSpec(
            mode="hybrid",
            weights={"rules": 0.8, "judge": 0.2},
            rules=[RuleSpec(id="exists", type="file_exists", points=1, params={"path": "summary.md"})],
        ),
    )
    run = AgentRunResult(
        task_id="summary",
        trial_id=1,
        status="success",
        started_at="s",
        finished_at="f",
        duration_seconds=1,
        workspace_path=str(tmp_path),
        log_dir=str(tmp_path),
        stdout_path="stdout.log",
        stderr_path="stderr.log",
        trace_path="trace.json",
        adapter_log_path="adapter.log",
        trace=Trace(),
    )

    result = HybridScorer(rule_scorer=RuleScorer(), judge_scorer=FixedJudge()).score(task, run)

    assert result.score == 0.9
    assert result.passed is True
