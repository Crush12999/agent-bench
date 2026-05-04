from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from agentbench.core.task import TaskSpec


WorkspacePolicy = Literal["all", "failed", "none"]


@dataclass(frozen=True)
class TrialPaths:
    workspace_dir: Path
    log_dir: Path
    stdout_path: Path
    stderr_path: Path
    adapter_log_path: Path
    trace_path: Path
    result_path: Path


class WorkspaceManager:
    def __init__(self, run_dir: Path, policy: WorkspacePolicy = "failed") -> None:
        self.run_dir = run_dir
        self.policy = policy

    def prepare_trial(self, task: TaskSpec, trial_id: int) -> TrialPaths:
        workspace_dir = self.run_dir / "workspaces" / task.id / f"trial-{trial_id}"
        log_dir = self.run_dir / "logs" / task.id / f"trial-{trial_id}"
        workspace_dir.mkdir(parents=True, exist_ok=True)
        log_dir.mkdir(parents=True, exist_ok=True)
        for seed in task.seed_files:
            source = Path(seed.source)
            if not source.is_absolute() and task.source_path is not None:
                source = (task.source_path.parent / source).resolve()
            target = workspace_dir / seed.dest
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        return TrialPaths(
            workspace_dir=workspace_dir,
            log_dir=log_dir,
            stdout_path=log_dir / "stdout.log",
            stderr_path=log_dir / "stderr.log",
            adapter_log_path=log_dir / "adapter.log",
            trace_path=log_dir / "trace.json",
            result_path=log_dir / "result.json",
        )

    def cleanup_trial(self, paths: TrialPaths, *, failed: bool) -> None:
        keep = self.policy == "all" or (self.policy == "failed" and failed)
        if keep:
            return
        if paths.workspace_dir.exists():
            shutil.rmtree(paths.workspace_dir)
