import subprocess
from pathlib import Path

import pytest

from agentbench.adapters.openclaw import OpenClawAgentLoop
from agentbench.core.task import RunConfig


def test_agent_command_uses_json_and_timeout():
    adapter = OpenClawAgentLoop(openclaw_binary="openclaw")

    command = adapter.build_agent_command("agent-1", "hello", 30)

    assert command == ["openclaw", "agent", "--agent", "agent-1", "--message", "hello", "--json", "--timeout", "30"]


def test_agent_command_uses_configured_model():
    adapter = OpenClawAgentLoop(openclaw_binary="openclaw", model="provider/model")

    command = adapter.build_agent_command("agent-1", "hello", 30)

    assert command == [
        "openclaw",
        "agent",
        "--agent",
        "agent-1",
        "--message",
        "hello",
        "--json",
        "--timeout",
        "30",
        "--model",
        "provider/model",
    ]


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


def test_preflight_passes_state_dir_environment(monkeypatch, tmp_path: Path):
    seen_env = {}

    def fake_run(command, **kwargs):
        seen_env.update(kwargs["env"])
        return subprocess.CompletedProcess(command, 0, stdout="[]", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    adapter = OpenClawAgentLoop(openclaw_binary="openclaw", state_dir=tmp_path / "state")

    result = adapter.preflight(RunConfig(adapter="openclaw", model="m"))

    assert result.ok is True
    assert seen_env["OPENCLAW_HOME"] == str(tmp_path / "state")
    assert seen_env["OPENCLAW_STATE_DIR"] == str(tmp_path / "state")
    assert seen_env["OPENCLAW_CONFIG_PATH"] == str(tmp_path / "state" / "openclaw.json")


def test_ensure_agent_recreates_stale_workspace(monkeypatch, tmp_path: Path):
    calls = []
    envs = []

    def fake_run(command, **kwargs):
        calls.append(command)
        envs.append(kwargs["env"])
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
    assert all(env["OPENCLAW_STATE_DIR"] == str(tmp_path / "state") for env in envs)


def test_ensure_agent_recreates_stale_workspace_from_json_list(monkeypatch, tmp_path: Path):
    calls = []
    old_workspace = tmp_path / "old"
    new_workspace = tmp_path / "new"

    def fake_run(command, **kwargs):
        calls.append(command)
        if command == ["openclaw", "agents", "list", "--json"]:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout='[{"id":"agent-1","workspace":"' + str(old_workspace) + '"}]',
                stderr="",
            )
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    adapter = OpenClawAgentLoop(openclaw_binary="openclaw", state_dir=tmp_path / "state")

    adapter.ensure_agent("agent-1", new_workspace, model="provider/model")

    assert ["openclaw", "agents", "delete", "agent-1", "--force"] in calls
    assert [
        "openclaw",
        "agents",
        "add",
        "agent-1",
        "--model",
        "provider/model",
        "--workspace",
        str(new_workspace),
        "--non-interactive",
    ] in calls


def test_ensure_agent_reports_creation_failure(monkeypatch, tmp_path: Path):
    def fake_run(command, **kwargs):
        if command == ["openclaw", "agents", "list"]:
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        if command[:3] == ["openclaw", "agents", "add"]:
            return subprocess.CompletedProcess(command, 2, stdout="", stderr="create failed")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    adapter = OpenClawAgentLoop(openclaw_binary="openclaw", state_dir=tmp_path / "state")

    with pytest.raises(RuntimeError, match="create failed"):
        adapter.ensure_agent("agent-1", tmp_path / "workspace", model="provider/model")


def test_ensure_agent_reports_delete_failure(monkeypatch, tmp_path: Path):
    def fake_run(command, **kwargs):
        if command == ["openclaw", "agents", "list", "--json"]:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout='[{"id":"agent-1","workspace":"/old/workspace"}]',
                stderr="",
            )
        if command[:3] == ["openclaw", "agents", "delete"]:
            return subprocess.CompletedProcess(command, 3, stdout="", stderr="delete failed")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    adapter = OpenClawAgentLoop(openclaw_binary="openclaw", state_dir=tmp_path / "state")

    with pytest.raises(RuntimeError, match="delete failed"):
        adapter.ensure_agent("agent-1", tmp_path / "workspace", model="provider/model")


def test_parse_transcript_normalizes_openclaw_message_events(tmp_path: Path):
    transcript = tmp_path / "session.jsonl"
    transcript.write_text(
        '{"type":"message","message":{"role":"assistant","content":[{"type":"text","text":"done"}]},"timestamp":"t"}\n'
        '{"type":"message","message":{"role":"user","content":[{"type":"text","text":"prompt"}]},"timestamp":"t"}\n',
        encoding="utf-8",
    )
    adapter = OpenClawAgentLoop(openclaw_binary="openclaw")

    trace = adapter.parse_transcript(transcript)

    assert len(trace.events) == 1
    assert trace.events[0].type == "assistant_message"
    assert trace.events[0].data["text"] == "done"


def test_prepare_workspace_removes_bootstrap_files(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    for name in ("BOOTSTRAP.md", "SOUL.md", "USER.md", "IDENTITY.md", "HEARTBEAT.md"):
        (workspace / name).write_text("bootstrap", encoding="utf-8")
    (workspace / "keep.txt").write_text("keep", encoding="utf-8")
    adapter = OpenClawAgentLoop(openclaw_binary="openclaw")

    adapter.prepare_workspace(workspace)

    assert not (workspace / "BOOTSTRAP.md").exists()
    assert (workspace / "keep.txt").exists()
