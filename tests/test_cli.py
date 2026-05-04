from pathlib import Path
import subprocess
import sys

from agentbench.cli import build_agent_loop, load_tasks_from_path, select_scorer
from agentbench.core.task import RunConfig
from agentbench.core.task import RuleSpec, ScoringSpec, TaskSpec
from agentbench.scorers.hybrid import HybridScorer
from agentbench.scorers.rules import RuleScorer


def test_load_tasks_from_directory(tmp_path: Path):
    (tmp_path / "a.yaml").write_text(
        "id: a\nname: A\nprompt: p\ntimeout_seconds: 1\nscoring:\n  mode: rules\n",
        encoding="utf-8",
    )
    (tmp_path / "b.yaml").write_text(
        "id: b\nname: B\nprompt: p\ntimeout_seconds: 1\nscoring:\n  mode: rules\n",
        encoding="utf-8",
    )

    tasks = load_tasks_from_path(tmp_path)

    assert [task.id for task in tasks] == ["a", "b"]


def test_select_scorer_by_mode():
    rules_task = TaskSpec(id="r", name="R", prompt="p", timeout_seconds=1, scoring=ScoringSpec(mode="rules"))
    hybrid_task = TaskSpec(
        id="h",
        name="H",
        prompt="p",
        timeout_seconds=1,
        scoring=ScoringSpec(
            mode="hybrid",
            rules=[RuleSpec(id="x", type="response_contains", points=1, params={"pattern": "x"})],
        ),
    )

    assert isinstance(select_scorer([rules_task]), RuleScorer)
    assert isinstance(select_scorer([hybrid_task]), HybridScorer)


def test_build_openclaw_agent_loop_uses_model_and_state_dir(tmp_path: Path):
    config = RunConfig(
        adapter="openclaw",
        model="provider/model",
        adapter_config={
            "openclaw_binary": "openclaw",
            "state_dir": str(tmp_path / "state"),
            "session_artifact_timeout_seconds": 3,
        },
    )

    adapter = build_agent_loop(config)

    assert adapter.model == "provider/model"
    assert adapter.state_dir == tmp_path / "state"
    assert adapter.session_artifact_timeout_seconds == 3


def test_module_entrypoint_runs_fake_example():
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agentbench.cli",
            "run",
            "--config",
            "examples/run.fake.yaml",
            "examples/tasks",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert result.stdout.strip().startswith("runs/")
