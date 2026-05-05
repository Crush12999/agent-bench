import json
from pathlib import Path

from agentbench.core.result import AgentRunResult
from agentbench.core.task import JudgeConfig, ScoringSpec, TaskSpec
from agentbench.core.trace import Trace, TraceEvent
from agentbench.scorers.judge import JudgeScorer


def make_judge_config(**overrides) -> JudgeConfig:
    values = {
        "provider": "openai",
        "model": "gpt-4o-mini",
        "base_url": "https://api.openai.com/v1",
        "api_key_env": "OPENAI_API_KEY",
        "temperature": 0.0,
        "timeout_seconds": 60,
        "max_tokens": 512,
        "max_context_chars": 20000,
        "max_tool_result_chars": 1000,
        "max_workspace_file_chars": 3000,
        "max_retries": 2,
        "retry_backoff_seconds": 1.0,
    }
    values.update(overrides)
    return JudgeConfig(**values)


def make_task() -> TaskSpec:
    return TaskSpec(
        id="judge-task",
        name="Judge Task",
        prompt="Write a concise summary.",
        timeout_seconds=30,
        pass_threshold=0.8,
        scoring=ScoringSpec(mode="judge", judge_rubric="Score accuracy and concision."),
    )


def make_run(tmp_path: Path, trace: Trace) -> AgentRunResult:
    return AgentRunResult(
        task_id="judge-task",
        trial_id=1,
        status="success",
        started_at="s",
        finished_at="f",
        duration_seconds=1.0,
        workspace_path=str(tmp_path),
        log_dir=str(tmp_path),
        stdout_path="stdout.log",
        stderr_path="stderr.log",
        trace_path="trace.json",
        adapter_log_path="adapter.log",
        trace=trace,
    )


def test_build_judge_prompt_includes_execution_trace_and_workspace_files(tmp_path: Path):
    (tmp_path / "summary.md").write_text("Final summary from workspace.", encoding="utf-8")
    (tmp_path / ".hidden").write_text("secret", encoding="utf-8")
    (tmp_path / ".cache").mkdir()
    (tmp_path / ".cache" / "secret.txt").write_text("hidden dir secret", encoding="utf-8")
    (tmp_path / "BOOTSTRAP.md").write_text("bootstrap", encoding="utf-8")
    trace = Trace(
        events=[
            TraceEvent(type="assistant_message", data={"text": "I will inspect the file."}),
            TraceEvent(type="tool_call", data={"tool": "read", "args": {"path": "report.txt", "query": "x" * 250}}),
            TraceEvent(type="tool_result", data={"content": "tool result " + "y" * 1200}),
            TraceEvent(type="file_event", data={"path": "summary.md", "event": "created"}),
            TraceEvent(type="error", data={"error": "minor warning"}),
        ]
    )
    scorer = JudgeScorer(make_judge_config(max_tool_result_chars=40, max_workspace_file_chars=20))

    prompt = scorer.build_prompt(make_task(), make_run(tmp_path, trace))

    assert "You are a grading function. Your ONLY job is to output a single JSON object." in prompt
    assert "CRITICAL RULES:" in prompt
    assert "Do NOT use tools." in prompt
    assert "Do NOT write prose outside JSON." in prompt
    assert "Respond with ONLY this JSON structure:" in prompt
    assert '{"scores": {"criterion_name": 0.0}, "total": 0.0, "notes": "brief justification"}' in prompt
    assert "## Task" in prompt
    assert "Write a concise summary." in prompt
    assert "## Grading Rubric" in prompt
    assert "Score accuracy and concision." in prompt
    assert "## Execution Status" in prompt
    assert "success" in prompt
    assert "## Agent Transcript Summary" in prompt
    assert "Assistant: I will inspect the file." in prompt
    assert "Tool: read(" in prompt
    assert "...[truncated]" in prompt
    assert "Result: tool result" in prompt
    assert "File event:" in prompt
    assert "Error: minor warning" in prompt
    assert "### File: summary.md" in prompt
    assert "Final summary from wo" in prompt
    assert "hidden dir secret" not in prompt
    assert "secret" not in prompt
    assert "bootstrap" not in prompt
