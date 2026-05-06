from pathlib import Path

from agentbench.cli import load_run_config, load_tasks_from_path


def test_openclaw_smoke_bundle_reuses_existing_smoke_task():
    original = load_tasks_from_path(Path("examples/tasks/openclaw_smoke.yaml"))[0]
    bundled = load_tasks_from_path(Path("examples/tasks/openclaw/openclaw_smoke.yaml"))[0]

    assert bundled.id == original.id
    assert bundled.name == original.name
    assert bundled.prompt == original.prompt
    assert bundled.pass_threshold == original.pass_threshold
    assert bundled.scoring.mode == original.scoring.mode
    assert [rule.id for rule in bundled.scoring.rules] == [
        rule.id for rule in original.scoring.rules
    ]


def test_openclaw_skills_judge_example_has_expected_scoring():
    task = load_tasks_from_path(Path("examples/tasks/openclaw/openclaw_skills_judge.yaml"))[0]

    assert task.id == "openclaw_skills_judge"
    assert task.timeout_seconds == 180
    assert task.scoring.mode == "judge"
    assert task.pass_threshold == 0.75
    assert task.scoring.judge_rubric
    assert task.scoring.rules == []
    assert "openclaw skills list --json" in task.prompt
    assert "skills_raw.json" in task.prompt
    assert "skills_assessment.md" in task.prompt
    assert "raw file and command output" in task.prompt
    assert "exact counts" in task.prompt
    assert "directly supported" in task.prompt
    assert "omit counts" in task.prompt
    assert "label uncertainty" in task.prompt
    assert "primary fact source" in task.scoring.judge_rubric


def test_openclaw_skills_hybrid_example_has_expected_scoring():
    task = load_tasks_from_path(Path("examples/tasks/openclaw/openclaw_skills_hybrid.yaml"))[0]

    assert task.id == "openclaw_skills_hybrid"
    assert task.timeout_seconds == 180
    assert task.scoring.mode == "hybrid"
    assert task.pass_threshold == 0.7
    assert task.scoring.weights == {"rules": 0.6, "judge": 0.4}
    assert task.scoring.judge_rubric
    assert [rule.id for rule in task.scoring.rules] == [
        "inventory_exists",
        "remediation_exists",
        "inventory_has_skills_key",
        "remediation_has_sections",
    ]
    assert "openclaw skills list --json" in task.prompt
    assert "skills_inventory.json" in task.prompt
    assert "skills_remediation.md" in task.prompt
    assert 'top-level "skills" key' in task.prompt
    assert "## Available Skills" in task.prompt
    assert "## Gaps Or Limits" in task.prompt
    assert "## Next Steps" in task.prompt


def test_load_openclaw_judge_and_hybrid_run_configs():
    judge_config = load_run_config(Path("examples/run.openclaw.judge.yaml"))
    hybrid_config = load_run_config(Path("examples/run.openclaw.hybrid.yaml"))

    assert judge_config.adapter == "openclaw"
    assert hybrid_config.adapter == "openclaw"
    assert judge_config.model == "minimax/MiniMax-M2.7"
    assert hybrid_config.model == "minimax/MiniMax-M2.7"
    assert judge_config.trials == 1
    assert hybrid_config.trials == 1
    assert judge_config.parallelism == 1
    assert hybrid_config.parallelism == 1
    assert judge_config.output_dir == "runs"
    assert hybrid_config.output_dir == "runs"
    assert judge_config.workspace_policy == "all"
    assert hybrid_config.workspace_policy == "all"
    assert judge_config.adapter_config["openclaw_binary"] == "openclaw"
    assert hybrid_config.adapter_config["openclaw_binary"] == "openclaw"
    assert judge_config.adapter_config["session_artifact_timeout_seconds"] == 15
    assert hybrid_config.adapter_config["session_artifact_timeout_seconds"] == 15
    assert judge_config.judge is not None
    assert hybrid_config.judge is not None
    assert judge_config.judge.provider == "openai"
    assert hybrid_config.judge.provider == "openai"
    assert judge_config.judge.model == "gpt-5.4"
    assert hybrid_config.judge.model == "gpt-5.4"
    assert judge_config.judge.base_url == "https://api.funai.vip/v1"
    assert hybrid_config.judge.base_url == "https://api.funai.vip/v1"
    assert judge_config.judge.api_key_env == "OPENAI_API_KEY"
    assert hybrid_config.judge.api_key_env == "OPENAI_API_KEY"
    assert judge_config.judge.temperature == 0
    assert hybrid_config.judge.temperature == 0
    assert judge_config.judge.timeout_seconds == 60
    assert hybrid_config.judge.timeout_seconds == 60
    assert judge_config.judge.max_tokens == 512
    assert hybrid_config.judge.max_tokens == 512


def test_openclaw_all_run_config_supports_expected_task_modes():
    config = load_run_config(Path("examples/run.openclaw.all.yaml"))
    tasks = load_tasks_from_path(Path("examples/tasks/openclaw"))

    tasks_by_id = {task.id: task for task in tasks}

    assert config.adapter == "openclaw"
    assert config.judge is not None
    assert config.judge.model == "gpt-5.4"
    assert config.judge.base_url == "https://api.funai.vip/v1"
    assert config.judge.api_key_env == "OPENAI_API_KEY"
    assert set(tasks_by_id) == {
        "openclaw_smoke",
        "openclaw_skills_judge",
        "openclaw_skills_hybrid",
    }
    assert tasks_by_id["openclaw_smoke"].scoring.mode == "rules"
    assert tasks_by_id["openclaw_skills_judge"].scoring.mode == "judge"
    assert tasks_by_id["openclaw_skills_hybrid"].scoring.mode == "hybrid"


def test_cli_accepts_openclaw_all_directory(monkeypatch):
    from agentbench import cli

    seen: dict[str, object] = {}

    class RecordingRunner:
        def __init__(self, config, agent_loop, scorer):
            seen["adapter"] = config.adapter

        def run(self, tasks):
            seen["task_ids"] = {task.id for task in tasks}
            return {"run_dir": "runs/example"}

    monkeypatch.setattr(cli, "build_agent_loop", lambda config: object())
    monkeypatch.setattr(cli, "select_scorer", lambda config, tasks: object())
    monkeypatch.setattr(cli, "Runner", RecordingRunner)

    exit_code = cli.main(
        [
            "run",
            "--config",
            "examples/run.openclaw.all.yaml",
            "examples/tasks/openclaw",
        ]
    )

    assert exit_code == 0
    assert seen["adapter"] == "openclaw"
    assert seen["task_ids"] == {
        "openclaw_smoke",
        "openclaw_skills_judge",
        "openclaw_skills_hybrid",
    }
