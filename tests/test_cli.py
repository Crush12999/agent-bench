from pathlib import Path
import os
import subprocess
import sys

import pytest

from agentbench.cli import build_agent_loop, load_tasks_from_path, select_scorer
from agentbench.core.result import AgentRunResult
from agentbench.core.task import JudgeConfig, RunConfig
from agentbench.core.task import RuleSpec, ScoringSpec, TaskSpec
from agentbench.core.trace import Trace
from agentbench.scorers.hybrid import HybridScorer
from agentbench.scorers.judge import JudgeScorer
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
    config = RunConfig(adapter="fake", model="fake")
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

    assert isinstance(select_scorer(config, [rules_task]), RuleScorer)
    assert isinstance(select_scorer(config, [hybrid_task]), HybridScorer)


def test_select_scorer_injects_judge_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    judge = JudgeConfig(
        provider="openai",
        model="judge-model",
        base_url="https://judge.example/v1",
        api_key_env="JUDGE_API_KEY",
    )
    config = RunConfig(adapter="fake", model="fake", judge=judge)
    task = TaskSpec(
        id="j",
        name="J",
        prompt="p",
        timeout_seconds=1,
        scoring=ScoringSpec(mode="judge", judge_rubric="score it"),
    )
    run = AgentRunResult(
        task_id="j",
        trial_id=1,
        status="success",
        started_at="2026-01-01T00:00:00Z",
        finished_at="2026-01-01T00:00:01Z",
        duration_seconds=1.0,
        workspace_path=str(tmp_path),
        log_dir=str(tmp_path),
        stdout_path=str(tmp_path / "stdout.txt"),
        stderr_path=str(tmp_path / "stderr.txt"),
        trace_path=str(tmp_path / "trace.json"),
        adapter_log_path=str(tmp_path / "adapter.log"),
        trace=Trace(),
    )
    monkeypatch.setattr(JudgeScorer, "call_judge", lambda self, _system, _user: '{"scores": {"overall": 0.8}, "total": 0.8}')

    scorer = select_scorer(config, [task])
    result = scorer.score(task, run)

    assert isinstance(scorer, JudgeScorer)
    assert scorer.config is judge
    assert result.status == "scored"
    assert result.score == 0.8


def test_select_scorer_injects_judge_config_for_hybrid():
    judge = JudgeConfig(
        provider="openai",
        model="judge-model",
        base_url="https://judge.example/v1",
        api_key_env="JUDGE_API_KEY",
    )
    config = RunConfig(adapter="fake", model="fake", judge=judge)
    task = TaskSpec(id="h", name="H", prompt="p", timeout_seconds=1, scoring=ScoringSpec(mode="hybrid"))

    scorer = select_scorer(config, [task])

    assert isinstance(scorer, HybridScorer)
    assert isinstance(scorer.rule_scorer, RuleScorer)
    assert isinstance(scorer.judge_scorer, JudgeScorer)
    assert scorer.judge_scorer.config is judge


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


def test_main_loads_cwd_dotenv(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    (tmp_path / ".env").write_text("JUDGE_API_KEY=from-dotenv\nEXISTING_KEY=from-dotenv\n", encoding="utf-8")
    (tmp_path / "config.yaml").write_text(
        """
adapter: fake
model: fake
output_dir: runs
judge:
  provider: openai
  model: judge-model
  api_key_env: JUDGE_API_KEY
""",
        encoding="utf-8",
    )
    (tmp_path / "task.yaml").write_text(
        """
id: judge-task
name: Judge Task
prompt: Say hi
timeout_seconds: 1
scoring:
  mode: judge
  judge_rubric: Score the response.
""",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("JUDGE_API_KEY", raising=False)
    monkeypatch.setenv("EXISTING_KEY", "already-set")
    seen_api_keys: list[str | None] = []

    def fake_call_judge(self: JudgeScorer, _system: str, _user: str) -> str:
        seen_api_keys.append(os.environ.get(self.config.api_key_env if self.config else ""))
        return '{"scores": {"overall": 1.0}, "total": 1.0}'

    monkeypatch.setattr(JudgeScorer, "call_judge", fake_call_judge)

    from agentbench.cli import main

    try:
        assert main(["run", "--config", "config.yaml", "task.yaml"]) == 0
        assert seen_api_keys == ["from-dotenv"]
        assert os.environ["EXISTING_KEY"] == "already-set"
    finally:
        os.environ.pop("JUDGE_API_KEY", None)
