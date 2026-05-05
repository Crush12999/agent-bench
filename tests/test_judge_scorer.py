import json
from pathlib import Path

import requests

from agentbench.core.result import AgentRunResult, CheckResult
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


def test_parse_judge_scores_total_notes(tmp_path: Path):
    scorer = JudgeScorer(make_judge_config())
    result = scorer.parse_judge_text(
        make_task(),
        make_run(tmp_path, Trace()),
        '{"scores": {"accuracy": 0.8, "style": 0.7}, "total": 0.9, "notes": "good"}',
    )

    assert result.status == "scored"
    assert result.score == 0.9
    assert result.passed is True
    assert result.notes == "good"
    assert [item.id for item in result.breakdown] == ["accuracy", "style"]
    assert all(isinstance(item, CheckResult) for item in result.breakdown)
    assert [item.score for item in result.breakdown] == [0.8, 0.7]
    assert [item.passed for item in result.breakdown] == [True, False]


def test_parse_judge_simplified_score_reason(tmp_path: Path):
    scorer = JudgeScorer(make_judge_config())
    result = scorer.parse_judge_text(make_task(), make_run(tmp_path, Trace()), '{"score": 0.7, "reason": "ok"}')

    assert result.status == "scored"
    assert result.score == 0.7
    assert result.passed is False
    assert result.notes == "ok"


def test_parse_judge_invalid_output_is_scoring_error(tmp_path: Path):
    scorer = JudgeScorer(make_judge_config())
    result = scorer.parse_judge_text(make_task(), make_run(tmp_path, Trace()), "not json")

    assert result.status == "scoring_error"
    assert result.score == 0.0


def test_parse_judge_invalid_structure_is_scoring_error(tmp_path: Path):
    scorer = JudgeScorer(make_judge_config())

    for output in [
        "[]",
        '{"scores": [], "total": 0.8}',
        '{"scores": {"accuracy": "high"}, "total": 0.8}',
        '{"total": 1.2}',
        '{"scores": {"accuracy": 2.0}, "total": 0.8}',
        '{"scores": {"accuracy": true}, "total": 0.8}',
        '{"score": true}',
        '{"notes": "missing total"}',
    ]:
        result = scorer.parse_judge_text(make_task(), make_run(tmp_path, Trace()), output)

        assert result.status == "scoring_error"
        assert result.score == 0.0


def test_score_supports_anthropic_provider(monkeypatch, tmp_path: Path):
    scorer = JudgeScorer(make_judge_config(provider="anthropic"))
    monkeypatch.setattr(scorer, "call_judge", lambda system_prompt, user_prompt: '{"total": 0.8, "notes": "ok"}')

    result = scorer.score(make_task(), make_run(tmp_path, Trace()))

    assert result.status == "scored"
    assert result.score == 0.8


def test_call_openai_chat_completions_protocol(monkeypatch):
    captured = {}

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": '{"total": 0.8, "notes": "ok"}'}}]}

    def fake_post(url, *, headers, json, timeout):
        captured.update(url=url, headers=headers, json=json, timeout=timeout)
        return Response()

    monkeypatch.setenv("JUDGE_API_KEY", "test-key")
    monkeypatch.setattr(requests, "post", fake_post)
    scorer = JudgeScorer(
        make_judge_config(
            base_url="https://judge.example/v1/",
            api_key_env="JUDGE_API_KEY",
            model="judge-model",
            temperature=0.2,
            timeout_seconds=30,
            max_tokens=256,
        )
    )

    content = scorer.call_judge("system prompt", "user prompt")

    assert content == '{"total": 0.8, "notes": "ok"}'
    assert captured == {
        "url": "https://judge.example/v1/chat/completions",
        "headers": {
            "Authorization": "Bearer test-key",
            "Content-Type": "application/json",
        },
        "json": {
            "model": "judge-model",
            "messages": [
                {"role": "system", "content": "system prompt"},
                {"role": "user", "content": "user prompt"},
            ],
            "temperature": 0.2,
            "max_tokens": 256,
        },
        "timeout": 30,
    }


def test_call_anthropic_messages_protocol(monkeypatch):
    captured = {}

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "content": [
                    {"type": "tool_use", "name": "ignored"},
                    {"type": "text", "text": '{"total": 0.9, "notes": "great"}'},
                ]
            }

    def fake_post(url, *, headers, json, timeout):
        captured.update(url=url, headers=headers, json=json, timeout=timeout)
        return Response()

    monkeypatch.setenv("JUDGE_API_KEY", "anthropic-key")
    monkeypatch.setattr(requests, "post", fake_post)
    scorer = JudgeScorer(
        make_judge_config(
            provider="anthropic",
            base_url="https://judge.example/",
            api_key_env="JUDGE_API_KEY",
            model="claude-judge",
            temperature=0.3,
            timeout_seconds=45,
            max_tokens=128,
        )
    )

    content = scorer.call_judge("system prompt", "user prompt")

    assert content == '{"total": 0.9, "notes": "great"}'
    assert captured == {
        "url": "https://judge.example/v1/messages",
        "headers": {
            "x-api-key": "anthropic-key",
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        "json": {
            "model": "claude-judge",
            "system": "system prompt",
            "messages": [{"role": "user", "content": "user prompt"}],
            "temperature": 0.3,
            "max_tokens": 128,
        },
        "timeout": 45,
    }
