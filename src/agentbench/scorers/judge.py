from __future__ import annotations

import json
from pathlib import Path

from agentbench.core.result import AgentRunResult, ScoreResult
from agentbench.core.task import JudgeConfig, TaskSpec


_SKIPPED_DIRS = {".git", ".openclaw", "__pycache__", "node_modules", "skills"}
_SKIPPED_FILES = {
    "BOOTSTRAP.md",
    "SOUL.md",
    "USER.md",
    "IDENTITY.md",
    "HEARTBEAT.md",
    "TOOLS.md",
    "AGENTS.md",
}


class JudgeScorer:
    """Judge 评分器占位实现。"""

    def __init__(self, config: JudgeConfig | None = None) -> None:
        """保存 Judge 配置，HTTP 调用由后续任务实现。"""
        self.config = config

    def score(self, task: TaskSpec, run: AgentRunResult) -> ScoreResult:
        """返回 scoring_error，避免在未配置 Judge 执行器时误报已评分。"""
        if not task.scoring.judge_rubric:
            return self._error(task, run, "judge_rubric missing")
        return self._error(task, run, "judge execution is not configured")

    def build_prompt(self, task: TaskSpec, run: AgentRunResult) -> str:
        """构造发送给 Judge 的任务、轨迹和工作区上下文。"""
        parts = [
            "## Task",
            f"Task ID: {task.id}",
            f"Name: {task.name}",
            "",
            task.prompt,
            "",
            "## Rubric",
            task.scoring.judge_rubric or "",
            "",
            "## Execution Status",
            f"Status: {run.status}",
            f"Duration: {run.duration_seconds:.4f}s",
            f"Error: {run.error}" if run.error else "Error: none",
            "",
            "## Execution Trace",
            self._summarize_trace(run),
            "",
            "## Workspace Files",
            self._read_workspace_files(Path(run.workspace_path)),
        ]
        return self._truncate("\n".join(parts), self._max_context_chars())

    def _summarize_trace(self, run: AgentRunResult) -> str:
        """把执行轨迹压缩为 Judge 可读的文本摘要。"""
        lines: list[str] = []
        for event in run.trace.events:
            data = event.data
            if event.type == "assistant_message":
                lines.append(f"Assistant: {self._truncate(str(data.get('text', '')), self._max_tool_result_chars())}")
            elif event.type == "tool_call":
                tool = str(data.get("tool", "unknown"))
                args = json.dumps(data.get("args", {}), ensure_ascii=False, sort_keys=True)
                lines.append(f"Tool: {tool}({self._truncate(args, self._max_tool_result_chars())})")
            elif event.type == "tool_result":
                content = data.get("content", data.get("text", ""))
                lines.append(f"Result: {self._truncate(str(content), self._max_tool_result_chars())}")
            elif event.type == "file_event":
                path = data.get("path", "")
                action = data.get("event", data.get("action", ""))
                lines.append(f"File event: {path} {action}".strip())
            elif event.type == "error":
                lines.append(f"Error: {data.get('error', data.get('message', ''))}")
        return "\n".join(lines) if lines else "(no trace events)"

    def _read_workspace_files(self, workspace: Path) -> str:
        """读取工作区中适合交给 Judge 的普通文本文件。"""
        if not workspace.exists():
            return "(workspace missing)"

        sections: list[str] = []
        for path in sorted(item for item in workspace.rglob("*") if item.is_file()):
            relative = path.relative_to(workspace)
            if self._should_skip(relative):
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            sections.append(
                "\n".join(
                    [
                        f"### File: {relative.as_posix()}",
                        self._truncate(content, self._max_workspace_file_chars()),
                    ]
                )
            )
        return "\n\n".join(sections) if sections else "(no workspace files)"

    def _error(self, task: TaskSpec, run: AgentRunResult, notes: str = "") -> ScoreResult:
        """构造 Judge 评分失败结果。"""
        return ScoreResult(
            task_id=task.id,
            trial_id=run.trial_id,
            status="scoring_error",
            score=0.0,
            passed=False,
            notes=notes,
        )

    def _should_skip(self, relative: Path) -> bool:
        """判断文件是否不应暴露给 Judge。"""
        parts = relative.parts
        return (
            relative.name in _SKIPPED_FILES
            or any(part.startswith(".") for part in parts)
            or any(part in _SKIPPED_DIRS for part in parts[:-1])
        )

    def _max_context_chars(self) -> int:
        """返回 Judge 上下文最大字符数。"""
        return self.config.max_context_chars if self.config else 20000

    def _max_tool_result_chars(self) -> int:
        """返回工具相关文本最大字符数。"""
        return self.config.max_tool_result_chars if self.config else 1000

    def _max_workspace_file_chars(self) -> int:
        """返回单个工作区文件最大字符数。"""
        return self.config.max_workspace_file_chars if self.config else 3000

    def _truncate(self, value: str, max_chars: int) -> str:
        """按字符数截断文本，并标记被截断的内容。"""
        if max_chars < 0 or len(value) <= max_chars:
            return value
        return f"{value[: max_chars + 1]}...[truncated]"
