from pathlib import Path

from agentbench.core.task import SeedFile, TaskSpec
from agentbench.core.workspace import WorkspaceManager


def test_create_trial_dirs_and_copy_seed_files(tmp_path: Path):
    fixture = tmp_path / "fixtures" / "report.txt"
    fixture.parent.mkdir()
    fixture.write_text("report", encoding="utf-8")
    task = TaskSpec(
        id="summary",
        name="Summary",
        prompt="write summary",
        timeout_seconds=60,
        seed_files=[SeedFile(source=str(fixture), dest="inputs/report.txt")],
    )

    manager = WorkspaceManager(tmp_path / "runs" / "run-1")
    trial = manager.prepare_trial(task, trial_id=1)

    assert (trial.workspace_dir / "inputs" / "report.txt").read_text(encoding="utf-8") == "report"
    assert trial.log_dir.name == "trial-1"
    assert trial.stdout_path.name == "stdout.log"


def test_cleanup_policy_failed_keeps_failed_and_removes_success(tmp_path: Path):
    task = TaskSpec(id="t", name="T", prompt="p", timeout_seconds=1)
    manager = WorkspaceManager(tmp_path / "runs" / "run-1", policy="failed")
    success_trial = manager.prepare_trial(task, trial_id=1)
    failed_trial = manager.prepare_trial(task, trial_id=2)

    manager.cleanup_trial(success_trial, failed=False)
    manager.cleanup_trial(failed_trial, failed=True)

    assert not success_trial.workspace_dir.exists()
    assert failed_trial.workspace_dir.exists()
