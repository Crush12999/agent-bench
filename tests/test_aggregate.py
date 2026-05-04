from agentbench.core.aggregate import aggregate_scores
from agentbench.core.result import ScoreResult


def score(task_id: str, trial_id: int, value: float, passed: bool) -> ScoreResult:
    return ScoreResult(task_id=task_id, trial_id=trial_id, status="scored", score=value, passed=passed)


def test_aggregate_pass_at_k_and_pass_k():
    summary = aggregate_scores(
        [
            score("a", 1, 1.0, True),
            score("a", 2, 0.0, False),
            score("b", 1, 1.0, True),
            score("b", 2, 1.0, True),
        ]
    )

    assert summary["average_score"] == 0.75
    assert summary["pass_at_1"] == 0.75
    assert summary["pass_at_k"] == 1.0
    assert summary["pass_k"] == 0.5
    assert summary["tasks"]["a"]["pass_at_k"] is True
    assert summary["tasks"]["a"]["pass_all_k"] is False
    assert summary["tasks"]["b"]["pass_all_k"] is True
