from pathlib import Path

import tomllib

import agentbench
from agentbench.core.task import load_run_config, load_task_spec


def test_project_metadata_and_version_are_defined():
    project_root = Path(__file__).resolve().parents[1]
    metadata = tomllib.loads((project_root / "pyproject.toml").read_text(encoding="utf-8"))

    assert metadata["project"]["name"] == "agentbench"
    assert metadata["project"]["version"] == agentbench.__version__
    assert metadata["project"]["scripts"]["agentbench"] == "agentbench.cli:main"


def test_openclaw_e2e_example_is_committed_and_loadable():
    project_root = Path(__file__).resolve().parents[1]
    config = load_run_config(project_root / "examples" / "run.openclaw.yaml")
    task = load_task_spec(project_root / "examples" / "tasks" / "openclaw_smoke.yaml")

    assert config.adapter == "openclaw"
    assert config.model == "minimax/MiniMax-M2.7"
    assert config.trials == 1
    assert config.workspace_policy == "all"
    assert config.adapter_config["session_artifact_timeout_seconds"] == 15
    assert task.id == "openclaw_smoke"
    assert task.pass_threshold == 1.0
    assert [rule.type for rule in task.scoring.rules] == ["file_exists", "file_contains"]
