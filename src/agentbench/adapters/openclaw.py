from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agentbench.adapters.base import PreflightResult
from agentbench.core.result import AgentRunResult
from agentbench.core.task import RunConfig, TaskSpec
from agentbench.core.trace import Trace, TraceEvent


class OpenClawAgentLoop:
    def __init__(
        self,
        openclaw_binary: str = "openclaw",
        model: str | None = None,
        state_dir: Path | None = None,
        session_artifact_timeout_seconds: int = 15,
    ) -> None:
        self.openclaw_binary = openclaw_binary
        self.model = model
        self.state_dir = state_dir
        self.session_artifact_timeout_seconds = session_artifact_timeout_seconds

    def preflight(self, config: RunConfig) -> PreflightResult:
        try:
            result = subprocess.run(
                [self.openclaw_binary, "agents", "list", "--json"],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
        except FileNotFoundError as exc:
            return PreflightResult(ok=False, message=str(exc))
        return PreflightResult(ok=result.returncode == 0, message=result.stderr.strip())

    def build_agent_command(self, agent_id: str, prompt: str, timeout_seconds: int) -> list[str]:
        return [
            self.openclaw_binary,
            "agent",
            "--agent",
            agent_id,
            "--message",
            prompt,
            "--json",
            "--timeout",
            str(timeout_seconds),
        ] + (["--model", self.model] if self.model else [])

    def run(
        self,
        task: TaskSpec,
        trial_id: int,
        workspace: Path,
        log_dir: Path,
        timeout_seconds: int,
    ) -> AgentRunResult:
        started_monotonic = time.monotonic()
        started = datetime.now(timezone.utc).isoformat()
        agent_id = self._agent_id(task.id, trial_id)
        stdout = ""
        stderr = ""
        adapter_log: list[str] = []
        status = "success"
        error = None
        proc: subprocess.Popen[str] | None = None
        try:
            self.ensure_agent(agent_id, workspace, model=self.model)
            self.prepare_workspace(workspace)
            proc = subprocess.Popen(
                self.build_agent_command(agent_id, task.prompt, timeout_seconds),
                cwd=str(workspace),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                preexec_fn=os.setsid,
            )
            stdout, stderr = proc.communicate(timeout=timeout_seconds)
            if proc.returncode not in (0, 255, -1):
                status = "error"
                error = stderr.strip() or f"openclaw exited with {proc.returncode}"
        except subprocess.TimeoutExpired:
            self.kill_process_group(proc)
            status = "timeout"
            error = "OpenClaw agent timed out"
        except Exception as exc:
            self.kill_process_group(proc)
            status = "error"
            error = str(exc)
        finished = datetime.now(timezone.utc).isoformat()
        if error:
            adapter_log.append(error)
        (log_dir / "stdout.log").write_text(stdout, encoding="utf-8")
        (log_dir / "stderr.log").write_text(stderr, encoding="utf-8")
        trace = self.load_trace(agent_id)
        if not trace.events:
            adapter_log.append("transcript not found or empty")
        (log_dir / "adapter.log").write_text("\n".join(adapter_log), encoding="utf-8")
        return AgentRunResult(
            task_id=task.id,
            trial_id=trial_id,
            status=status,
            started_at=started,
            finished_at=finished,
            duration_seconds=round(time.monotonic() - started_monotonic, 4),
            workspace_path=str(workspace),
            log_dir=str(log_dir),
            stdout_path=str(log_dir / "stdout.log"),
            stderr_path=str(log_dir / "stderr.log"),
            trace_path=str(log_dir / "trace.json"),
            adapter_log_path=str(log_dir / "adapter.log"),
            trace=trace,
            error=error,
        )

    def ensure_agent(self, agent_id: str, workspace: Path, model: str | None = None) -> None:
        workspace.mkdir(parents=True, exist_ok=True)
        existing_agents = self._list_existing_agents()
        normalized_id = self._normalize_agent_id(agent_id)
        if agent_id.lower() in existing_agents or normalized_id in existing_agents:
            current_workspace = self._get_agent_workspace(agent_id)
            if current_workspace is not None and current_workspace.resolve() == workspace.resolve():
                self._configure_models_json(agent_id, model)
                self._delete_stale_sessions_store(agent_id)
                return
            delete_name = normalized_id if normalized_id in existing_agents else agent_id
            subprocess.run(
                [self.openclaw_binary, "agents", "delete", delete_name, "--force"],
                capture_output=True,
                text=True,
                check=False,
            )
        command = [self.openclaw_binary, "agents", "add", agent_id]
        if model:
            command.extend(["--model", model])
        command.extend(["--workspace", str(workspace), "--non-interactive"])
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or f"openclaw agents add exited with {result.returncode}"
            raise RuntimeError(detail)
        self._configure_models_json(agent_id, model)
        self._delete_stale_sessions_store(agent_id)

    def prepare_workspace(self, workspace: Path) -> None:
        for bootstrap_file in ("BOOTSTRAP.md", "SOUL.md", "USER.md", "IDENTITY.md", "HEARTBEAT.md"):
            path = workspace / bootstrap_file
            if path.exists():
                try:
                    path.unlink()
                except OSError:
                    pass

    def load_trace(self, agent_id: str) -> Trace:
        sessions_dir = self.agent_sessions_dir(agent_id)
        deadline = time.monotonic() + self.session_artifact_timeout_seconds
        while time.monotonic() <= deadline:
            path = self.resolve_transcript_path(sessions_dir, "")
            if path is not None:
                return self.parse_transcript(path)
            time.sleep(0.25)
        return Trace(events=[])

    def resolve_transcript_path(self, sessions_dir: Path, session_id: str) -> Path | None:
        if not sessions_dir.exists():
            return None
        for candidate_session_id in [session_id, *self._session_ids_from_metadata(sessions_dir)]:
            normalized = str(candidate_session_id or "").strip()
            if not normalized:
                continue
            for suffix in (".jsonl", ".ndjson"):
                transcript_path = sessions_dir / f"{normalized}{suffix}"
                if transcript_path.exists():
                    return transcript_path

        sessions_path = sessions_dir / "sessions.json"
        if sessions_path.exists():
            try:
                raw = json.loads(sessions_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                raw = None
            if isinstance(raw, dict):
                latest_file: tuple[int, Path] | None = None
                for value in raw.values():
                    if not isinstance(value, dict):
                        continue
                    session_file = value.get("sessionFile")
                    if not isinstance(session_file, str) or not session_file.strip():
                        continue
                    path = Path(session_file)
                    if not path.exists():
                        continue
                    updated_at = int(value.get("updatedAt", 0) or 0)
                    if latest_file is None or updated_at > latest_file[0]:
                        latest_file = (updated_at, path)
                if latest_file is not None:
                    return latest_file[1]

        candidates = sorted(
            [*sessions_dir.glob("*.jsonl"), *sessions_dir.glob("*.ndjson")],
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        return candidates[0] if candidates else None

    def parse_transcript(self, path: Path) -> Trace:
        events: list[TraceEvent] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                raw: dict[str, Any] = json.loads(line)
            except json.JSONDecodeError:
                events.append(TraceEvent(type="error", data={"raw": line}))
                continue
            if raw.get("type") in {"tool_call", "tool_result", "assistant_message", "file_event", "error"}:
                events.append(TraceEvent(type=raw["type"], data=raw))
            elif raw.get("type") == "message":
                event = self._trace_event_from_message(raw)
                if event is not None:
                    events.append(event)
            elif raw.get("text"):
                events.append(TraceEvent(type="assistant_message", data={"text": raw["text"]}))
        return Trace(events=events)

    def _trace_event_from_message(self, raw: dict[str, Any]) -> TraceEvent | None:
        message = raw.get("message")
        if not isinstance(message, dict) or message.get("role") != "assistant":
            return None
        text_parts: list[str] = []
        content = message.get("content")
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_parts.append(str(item.get("text", "")))
        elif isinstance(content, str):
            text_parts.append(content)
        text = "".join(text_parts).strip()
        if not text:
            return None
        return TraceEvent(type="assistant_message", timestamp=raw.get("timestamp"), data={"text": text, "raw": raw})

    def kill_process_group(self, proc: subprocess.Popen[str] | None) -> None:
        if proc is None:
            return
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            proc.wait(timeout=5)
        except Exception:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except Exception:
                pass

    def agent_sessions_dir(self, agent_id: str) -> Path:
        return self._agent_store_dir(agent_id) / "sessions"

    def _agent_store_dir(self, agent_id: str) -> Path:
        base = self.state_dir if self.state_dir is not None else Path.home() / ".openclaw"
        return base / "agents" / agent_id

    def _agent_id(self, task_id: str, trial_id: int) -> str:
        return f"agentbench-{task_id}-trial-{trial_id}".replace("_", "-").lower()

    def _normalize_agent_id(self, agent_id: str) -> str:
        return agent_id.replace(":", "-").lower()

    def _list_existing_agents(self) -> set[str]:
        try:
            result = subprocess.run(
                [self.openclaw_binary, "agents", "list"],
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError:
            return set()
        if result.returncode != 0:
            return set()
        existing_agents: set[str] = set()
        for line in result.stdout.splitlines():
            stripped = line.strip()
            if stripped.startswith("- "):
                name_part = stripped[2:].split()[0] if stripped[2:].strip() else ""
                if name_part:
                    existing_agents.add(name_part.lower())
        return existing_agents

    def _get_agent_workspace(self, agent_id: str) -> Path | None:
        try:
            result = subprocess.run(
                [self.openclaw_binary, "agents", "list"],
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError:
            return None
        if result.returncode != 0:
            return None
        normalized_id = self._normalize_agent_id(agent_id)
        found_agent = False
        for line in result.stdout.splitlines():
            stripped = line.strip()
            if stripped.startswith(f"- {agent_id}") or stripped.startswith(f"- {normalized_id}"):
                found_agent = True
            elif found_agent and "Workspace:" in line:
                workspace_str = line.split("Workspace:", 1)[1].strip()
                if workspace_str.startswith("~/"):
                    workspace_str = str(Path.home() / workspace_str[2:])
                return Path(workspace_str)
            elif found_agent and stripped.startswith("- "):
                break
        return None

    def _session_ids_from_metadata(self, sessions_dir: Path) -> list[str]:
        sessions_path = sessions_dir / "sessions.json"
        if not sessions_path.exists():
            return []
        try:
            raw = json.loads(sessions_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        if not isinstance(raw, dict):
            return []
        ids: list[str] = []
        for value in raw.values():
            if not isinstance(value, dict):
                continue
            for candidate in (value.get("sessionId"), value.get("systemPromptReport", {}).get("sessionId") if isinstance(value.get("systemPromptReport"), dict) else None):
                if isinstance(candidate, str) and candidate.strip():
                    ids.append(candidate.strip())
            session_file = value.get("sessionFile")
            if isinstance(session_file, str) and session_file.strip():
                ids.append(Path(session_file).stem)
        return ids

    def _configure_models_json(self, agent_id: str, model: str | None) -> None:
        if not model:
            return
        agent_dir = self._agent_store_dir(agent_id) / "agent"
        agent_dir.mkdir(parents=True, exist_ok=True)
        target = agent_dir / "models.json"
        main_models = (self.state_dir if self.state_dir is not None else Path.home() / ".openclaw") / "agents" / "main" / "agent" / "models.json"
        if main_models.exists():
            shutil.copy2(main_models, target)
            try:
                data = json.loads(target.read_text(encoding="utf-8-sig"))
                if "/" in model:
                    provider_name, model_name = model.split("/", 1)
                    data["defaultProvider"] = provider_name
                    data["defaultModel"] = model_name
                else:
                    data["defaultModel"] = model
                target.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            except (json.JSONDecodeError, OSError):
                return

    def _delete_stale_sessions_store(self, agent_id: str) -> None:
        sessions_store = self.agent_sessions_dir(agent_id) / "sessions.json"
        if sessions_store.exists():
            try:
                sessions_store.unlink()
            except OSError:
                return
