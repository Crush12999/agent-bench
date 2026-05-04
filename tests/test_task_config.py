from pathlib import Path

from agentbench.core.task import load_run_config, load_task_spec


def test_load_task_spec(tmp_path: Path):
    task_path = tmp_path / "task.yaml"
    task_path.write_text(
        """
id: summary
name: Summary Task
timeout_seconds: 120
pass_threshold: 0.6
prompt: |
  Write summary.md from report.txt.
seed_files:
  - source: fixtures/report.txt
    dest: report.txt
scoring:
  mode: rules
  rules:
    - id: summary_exists
      type: file_exists
      points: 1
      params:
        path: summary.md
metadata:
  category: smoke
""",
        encoding="utf-8",
    )

    task = load_task_spec(task_path)

    assert task.id == "summary"
    assert task.timeout_seconds == 120
    assert task.pass_threshold == 0.6
    assert task.seed_files[0].dest == "report.txt"
    assert task.scoring.mode == "rules"
    assert task.scoring.rules[0].type == "file_exists"


def test_load_run_config(tmp_path: Path):
    config_path = tmp_path / "run.yaml"
    config_path.write_text(
        """
run:
  adapter: openclaw
  model: openrouter/anthropic/claude-sonnet-4
  trials: 3
  parallelism: 2
  output_dir: runs
  workspace_policy: failed
  judge:
    mode: agent
    model: openrouter/anthropic/claude-haiku-4
  adapter_config:
    openclaw_binary: openclaw
    session_artifact_timeout_seconds: 15
""",
        encoding="utf-8",
    )

    config = load_run_config(config_path)

    assert config.adapter == "openclaw"
    assert config.model == "openrouter/anthropic/claude-sonnet-4"
    assert config.trials == 3
    assert config.parallelism == 2
    assert config.workspace_policy == "failed"
    assert config.judge is not None
    assert config.judge.mode == "agent"
    assert config.adapter_config["session_artifact_timeout_seconds"] == 15
