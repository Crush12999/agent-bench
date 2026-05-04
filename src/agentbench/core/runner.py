from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4

from agentbench.adapters.base import AgentLoop
from agentbench.core.aggregate import aggregate_scores
from agentbench.core.result import AgentRunResult, ScoreResult
from agentbench.core.task import RunConfig, TaskSpec
from agentbench.core.workspace import TrialPaths, WorkspaceManager
from agentbench.reporters.json import append_jsonl, write_json
from agentbench.scorers.base import Scorer


class Runner:
    def __init__(self, config: RunConfig, agent_loop: AgentLoop, scorer: Scorer) -> None:
        self.config = config
        self.agent_loop = agent_loop
        self.scorer = scorer
        self._write_lock = Lock()

    def run(self, tasks: list[TaskSpec]) -> dict[str, Any]:
        preflight = self.agent_loop.preflight(self.config)
        if not preflight.ok:
            raise RuntimeError(preflight.message)
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
        run_dir = Path(self.config.output_dir) / run_id
        workspace_manager = WorkspaceManager(run_dir, policy=self.config.workspace_policy)
        trial_rows: list[dict[str, Any]] = []
        scores: list[ScoreResult] = []

        with ThreadPoolExecutor(max_workers=max(self.config.parallelism, 1)) as executor:
            futures = []
            for task in tasks:
                for trial_id in range(1, self.config.trials + 1):
                    futures.append(executor.submit(self._run_one, workspace_manager, task, trial_id))
            for future in as_completed(futures):
                run_result, score_result, row, paths = future.result()
                trial_rows.append(row)
                scores.append(score_result)
                failed = run_result.status != "success" or not score_result.passed
                workspace_manager.cleanup_trial(paths, failed=failed)
                with self._write_lock:
                    append_jsonl(run_dir / "trials.jsonl", row)

        summary = aggregate_scores(scores)
        payload = {"run_id": run_id, "run_dir": str(run_dir), "summary": summary, "trials": trial_rows}
        write_json(run_dir / "run.json", payload)
        return payload

    def _run_one(
        self,
        workspace_manager: WorkspaceManager,
        task: TaskSpec,
        trial_id: int,
    ) -> tuple[AgentRunResult, ScoreResult, dict[str, Any], TrialPaths]:
        paths = workspace_manager.prepare_trial(task, trial_id)
        run_result = self.agent_loop.run(task, trial_id, paths.workspace_dir, paths.log_dir, task.timeout_seconds)
        score_result = self.scorer.score(task, run_result)
        write_json(paths.trace_path, run_result.trace.to_dict())
        write_json(paths.result_path, {"run": run_result.to_dict(), "score": score_result.to_dict()})
        row = {
            "task_id": task.id,
            "trial_id": trial_id,
            "status": run_result.status,
            "score": score_result.score,
            "passed": score_result.passed,
            "duration_seconds": run_result.duration_seconds,
            "workspace_path": run_result.workspace_path,
            "log_dir": run_result.log_dir,
            "error": run_result.error,
        }
        return run_result, score_result, row, paths
