import json
from pathlib import Path

from agentbench.adapters.fake import FakeAgentLoop
from agentbench.core.runner import Runner
from agentbench.core.task import RuleSpec, RunConfig, ScoringSpec, TaskSpec
from agentbench.scorers.rules import RuleScorer


def task(task_id: str) -> TaskSpec:
    return TaskSpec(
        id=task_id,
        name=task_id,
        prompt="write summary",
        timeout_seconds=5,
        scoring=ScoringSpec(
            mode="rules",
            rules=[RuleSpec(id="exists", type="file_exists", points=1, params={"path": "summary.md"})],
        ),
    )


def test_runner_writes_trial_logs_and_summary(tmp_path: Path):
    config = RunConfig(
        adapter="fake",
        model="fake",
        trials=2,
        parallelism=2,
        output_dir=str(tmp_path),
        workspace_policy="all",
    )
    runner = Runner(config=config, agent_loop=FakeAgentLoop(), scorer=RuleScorer())

    result = runner.run([task("a"), task("b")])

    run_dir = Path(result["run_dir"])
    assert (run_dir / "run.json").exists()
    rows = (run_dir / "trials.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(rows) == 4
    first = json.loads(rows[0])
    assert Path(first["log_dir"], "result.json").exists()
    assert result["summary"]["pass_at_k"] == 1.0


class FailingOnceAgentLoop(FakeAgentLoop):
    def run(self, task, trial_id, workspace, log_dir, timeout_seconds):
        if task.id == "bad":
            raise RuntimeError("agent exploded")
        return super().run(task, trial_id, workspace, log_dir, timeout_seconds)


def test_runner_records_trial_errors_without_aborting_run(tmp_path: Path):
    config = RunConfig(
        adapter="fake",
        model="fake",
        trials=1,
        parallelism=2,
        output_dir=str(tmp_path),
        workspace_policy="all",
    )
    runner = Runner(config=config, agent_loop=FailingOnceAgentLoop(), scorer=RuleScorer())

    result = runner.run([task("good"), task("bad")])

    run_dir = Path(result["run_dir"])
    rows = [json.loads(line) for line in (run_dir / "trials.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 2
    bad = next(row for row in rows if row["task_id"] == "bad")
    good = next(row for row in rows if row["task_id"] == "good")
    assert bad["status"] == "error"
    assert bad["passed"] is False
    assert "agent exploded" in bad["error"]
    assert Path(bad["log_dir"], "result.json").exists()
    assert good["status"] == "success"


class ExplodingScorer:
    def score(self, task, run):
        raise RuntimeError("scorer exploded")


def test_runner_records_scoring_errors_without_replacing_run_result(tmp_path: Path):
    config = RunConfig(
        adapter="fake",
        model="fake",
        trials=1,
        parallelism=1,
        output_dir=str(tmp_path),
        workspace_policy="all",
    )
    runner = Runner(config=config, agent_loop=FakeAgentLoop(), scorer=ExplodingScorer())

    result = runner.run([task("scoring")])

    run_dir = Path(result["run_dir"])
    row = json.loads((run_dir / "trials.jsonl").read_text(encoding="utf-8").strip())
    result_json = json.loads(Path(row["log_dir"], "result.json").read_text(encoding="utf-8"))
    assert row["status"] == "success"
    assert row["score"] == 0.0
    assert row["passed"] is False
    assert result_json["run"]["status"] == "success"
    assert result_json["score"]["status"] == "scoring_error"
    assert "scorer exploded" in result_json["score"]["notes"]
