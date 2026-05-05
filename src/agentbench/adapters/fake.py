from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from agentbench.adapters.base import PreflightResult
from agentbench.core.result import AgentRunResult
from agentbench.core.task import RunConfig, TaskSpec
from agentbench.core.trace import Trace, TraceEvent


class FakeAgentLoop:
    """用于测试和示例的本地假 Agent 适配器。"""

    def preflight(self, config: RunConfig) -> PreflightResult:
        """假适配器没有外部依赖，预检始终通过。"""
        return PreflightResult(ok=True)

    def run(
        self,
        task: TaskSpec,
        trial_id: int,
        workspace: Path,
        log_dir: Path,
        timeout_seconds: int,
    ) -> AgentRunResult:
        """写入固定输出，模拟一次成功的 Agent 执行。"""
        started = datetime.now(timezone.utc).isoformat()
        output = workspace / "summary.md"
        output.write_text(f"done {task.id}", encoding="utf-8")
        (log_dir / "stdout.log").write_text("fake stdout", encoding="utf-8")
        (log_dir / "stderr.log").write_text("", encoding="utf-8")
        (log_dir / "adapter.log").write_text("fake adapter", encoding="utf-8")
        finished = datetime.now(timezone.utc).isoformat()
        return AgentRunResult(
            task_id=task.id,
            trial_id=trial_id,
            status="success",
            started_at=started,
            finished_at=finished,
            duration_seconds=0.0,
            workspace_path=str(workspace),
            log_dir=str(log_dir),
            stdout_path=str(log_dir / "stdout.log"),
            stderr_path=str(log_dir / "stderr.log"),
            trace_path=str(log_dir / "trace.json"),
            adapter_log_path=str(log_dir / "adapter.log"),
            trace=Trace(events=[TraceEvent(type="assistant_message", data={"text": "done"})]),
        )
