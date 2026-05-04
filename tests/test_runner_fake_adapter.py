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
