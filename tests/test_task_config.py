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
    provider: openai
    model: openrouter/anthropic/claude-haiku-4
    base_url: https://openrouter.ai/api/v1
    api_key_env: OPENROUTER_API_KEY
    temperature: 0.2
    timeout_seconds: 30
    max_tokens: 256
    max_context_chars: 10000
    max_tool_result_chars: 500
    max_workspace_file_chars: 1200
    max_retries: 3
    retry_backoff_seconds: 0.5
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
    assert config.judge.provider == "openai"
    assert config.judge.model == "openrouter/anthropic/claude-haiku-4"
    assert config.judge.base_url == "https://openrouter.ai/api/v1"
    assert config.judge.api_key_env == "OPENROUTER_API_KEY"
    assert config.judge.temperature == 0.2
    assert config.judge.timeout_seconds == 30
    assert config.judge.max_tokens == 256
    assert config.judge.max_context_chars == 10000
    assert config.judge.max_tool_result_chars == 500
    assert config.judge.max_workspace_file_chars == 1200
    assert config.judge.max_retries == 3
    assert config.judge.retry_backoff_seconds == 0.5
    assert config.adapter_config["session_artifact_timeout_seconds"] == 15


def test_load_run_config_with_judge_defaults(tmp_path: Path):
    config_path = tmp_path / "run.yaml"
    config_path.write_text(
        """
run:
  adapter: fake
  model: fake
  judge:
    provider: anthropic
    model: claude-3-5-haiku-latest
""",
        encoding="utf-8",
    )

    config = load_run_config(config_path)

    assert config.judge is not None
    assert config.judge.provider == "anthropic"
    assert config.judge.base_url == "https://api.anthropic.com"
    assert config.judge.api_key_env == "ANTHROPIC_API_KEY"
    assert config.judge.temperature == 0.0
    assert config.judge.timeout_seconds == 60
    assert config.judge.max_tokens == 512
    assert config.judge.max_context_chars == 20000
    assert config.judge.max_tool_result_chars == 1000
    assert config.judge.max_workspace_file_chars == 3000
    assert config.judge.max_retries == 2
    assert config.judge.retry_backoff_seconds == 1.0
