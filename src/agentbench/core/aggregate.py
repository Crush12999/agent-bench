from __future__ import annotations

import statistics
from collections import defaultdict
from typing import Any

from agentbench.core.result import ScoreResult


def aggregate_scores(scores: list[ScoreResult]) -> dict[str, Any]:
    by_task: dict[str, list[ScoreResult]] = defaultdict(list)
    for score in scores:
        by_task[score.task_id].append(score)

    task_summaries: dict[str, dict[str, Any]] = {}
    for task_id, task_scores in by_task.items():
        values = [item.score for item in task_scores]
        pass_count = sum(1 for item in task_scores if item.passed)
        trials = len(task_scores)
        task_summaries[task_id] = {
            "trials": trials,
            "avg_score": round(sum(values) / trials, 4) if trials else 0.0,
            "pass_count": pass_count,
            "pass_rate": round(pass_count / trials, 4) if trials else 0.0,
            "pass_at_k": pass_count > 0,
            "pass_all_k": trials > 0 and pass_count == trials,
            "score_stddev": round(statistics.pstdev(values), 6) if len(values) > 1 else 0.0,
        }

    all_scores = [item.score for item in scores]
    all_passes = [item.passed for item in scores]
    task_count = len(task_summaries)
    return {
        "average_score": round(sum(all_scores) / len(all_scores), 4) if all_scores else 0.0,
        "pass_at_1": round(sum(1 for item in all_passes if item) / len(all_passes), 4) if all_passes else 0.0,
        "pass_at_k": round(
            sum(1 for item in task_summaries.values() if item["pass_at_k"]) / task_count,
            4,
        )
        if task_count
        else 0.0,
        "pass_k": round(
            sum(1 for item in task_summaries.values() if item["pass_all_k"]) / task_count,
            4,
        )
        if task_count
        else 0.0,
        "avg_score_stddev": round(
            sum(item["score_stddev"] for item in task_summaries.values()) / task_count,
            6,
        )
        if task_count
        else 0.0,
        "tasks": task_summaries,
    }
