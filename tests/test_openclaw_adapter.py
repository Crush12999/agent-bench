import subprocess
from pathlib import Path

from agentbench.adapters.openclaw import OpenClawAgentLoop
from agentbench.core.task import RunConfig


def test_agent_command_uses_json_and_timeout():
    adapter = OpenClawAgentLoop(openclaw_binary="openclaw")

    command = adapter.build_agent_command("agent-1", "hello", 30)

    assert command == ["openclaw", "agent", "--agent", "agent-1", "--message", "hello", "--json", "--timeout", "30"]


def test_resolve_transcript_prefers_sessions_json_session_file(tmp_path: Path):
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    transcript = sessions / "real.jsonl"
    transcript.write_text('{"type":"assistant_message","text":"done"}\n', encoding="utf-8")
    (sessions / "sessions.json").write_text(
        '{"x":{"sessionId":"real","sessionFile":"' + str(transcript) + '","updatedAt":1}}',
        encoding="utf-8",
    )
    adapter = OpenClawAgentLoop(openclaw_binary="openclaw")

    resolved = adapter.resolve_transcript_path(sessions, "requested")

    assert resolved == transcript


def test_preflight_reports_missing_binary(monkeypatch):
    def raise_missing(*args, **kwargs):
        raise FileNotFoundError("missing")

    monkeypatch.setattr(subprocess, "run", raise_missing)
    adapter = OpenClawAgentLoop(openclaw_binary="missing-openclaw")

    result = adapter.preflight(RunConfig(adapter="openclaw", model="m"))

    assert result.ok is False
    assert "missing" in result.message


def test_ensure_agent_recreates_stale_workspace(monkeypatch, tmp_path: Path):
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        if command == ["openclaw", "agents", "list"]:
            return subprocess.CompletedProcess(command, 0, stdout="- agent-1\n  Workspace: /old/workspace\n", stderr="")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    adapter = OpenClawAgentLoop(openclaw_binary="openclaw", state_dir=tmp_path / "state")

    adapter.ensure_agent("agent-1", tmp_path / "workspace", model="provider/model")

    assert ["openclaw", "agents", "delete", "agent-1", "--force"] in calls
    assert [
        "openclaw",
        "agents",
        "add",
        "agent-1",
        "--model",
        "provider/model",
        "--workspace",
        str(tmp_path / "workspace"),
        "--non-interactive",
    ] in calls
