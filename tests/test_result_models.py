from agentbench.core.result import AgentRunResult, CheckResult, ScoreResult
from agentbench.core.trace import Trace, TraceEvent


def test_trace_and_results_serialize_to_dicts():
    trace = Trace(events=[TraceEvent(type="assistant_message", data={"text": "done"})])
    run = AgentRunResult(
        task_id="summary",
        trial_id=1,
        status="success",
        started_at="2026-05-03T00:00:00Z",
        finished_at="2026-05-03T00:00:01Z",
        duration_seconds=1.0,
        workspace_path="/tmp/work",
        log_dir="/tmp/logs",
        stdout_path="/tmp/logs/stdout.log",
        stderr_path="/tmp/logs/stderr.log",
        trace_path="/tmp/logs/trace.json",
        adapter_log_path="/tmp/logs/adapter.log",
        trace=trace,
    )
    score = ScoreResult(
        task_id="summary",
        trial_id=1,
        status="scored",
        score=1.0,
        passed=True,
        breakdown=[CheckResult(id="exists", score=1.0, points=1.0, passed=True, detail="ok")],
    )

    assert run.to_dict()["trace"]["events"][0]["data"]["text"] == "done"
    assert score.to_dict()["breakdown"][0]["id"] == "exists"
