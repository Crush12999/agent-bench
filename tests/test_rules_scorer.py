from pathlib import Path

from agentbench.core.result import AgentRunResult
from agentbench.core.task import RuleSpec, ScoringSpec, TaskSpec
from agentbench.core.trace import Trace, TraceEvent
from agentbench.scorers.rules import RuleScorer


def run_result(tmp_path: Path, trace: Trace) -> AgentRunResult:
    return AgentRunResult(
        task_id="summary",
        trial_id=1,
        status="success",
        started_at="s",
        finished_at="f",
        duration_seconds=1,
        workspace_path=str(tmp_path),
        log_dir=str(tmp_path / "logs"),
        stdout_path="stdout.log",
        stderr_path="stderr.log",
        trace_path="trace.json",
        adapter_log_path="adapter.log",
        trace=trace,
    )


def test_file_and_response_rules(tmp_path: Path):
    (tmp_path / "summary.md").write_text("safe summary", encoding="utf-8")
    task = TaskSpec(
        id="summary",
        name="Summary",
        prompt="p",
        timeout_seconds=1,
        scoring=ScoringSpec(
            mode="rules",
            rules=[
                RuleSpec(id="exists", type="file_exists", points=1, params={"path": "summary.md"}),
                RuleSpec(
                    id="contains",
                    type="file_contains",
                    points=1,
                    params={"path": "summary.md", "patterns": ["safe"]},
                ),
                RuleSpec(id="reply", type="response_contains", points=1, params={"patterns": ["done"]}),
            ],
        ),
    )
    trace = Trace(events=[TraceEvent(type="assistant_message", data={"text": "done"})])

    result = RuleScorer().score(task, run_result(tmp_path, trace))

    assert result.score == 1.0
    assert result.passed is True
    assert len(result.breakdown) == 3


def test_tool_call_rules(tmp_path: Path):
    task = TaskSpec(
        id="tool",
        name="Tool",
        prompt="p",
        timeout_seconds=1,
        scoring=ScoringSpec(
            mode="rules",
            rules=[
                RuleSpec(id="called", type="tool_called", points=1, params={"tool": "write"}),
                RuleSpec(
                    id="arg",
                    type="tool_arg_contains",
                    points=1,
                    params={"tool": "write", "pattern": "summary.md"},
                ),
            ],
        ),
    )
    trace = Trace(events=[TraceEvent(type="tool_call", data={"tool": "write", "args": {"path": "summary.md"}})])

    result = RuleScorer().score(task, run_result(tmp_path, trace))

    assert result.score == 1.0
    assert result.passed is True
