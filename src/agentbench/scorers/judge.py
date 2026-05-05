from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Callable

import requests

from agentbench.core.result import AgentRunResult, CheckResult, ScoreResult
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
    """Judge 评分器。"""

    def __init__(self, config: JudgeConfig | None = None) -> None:
        """保存 Judge 配置。"""
        self.config = config

    def score(self, task: TaskSpec, run: AgentRunResult) -> ScoreResult:
        """调用 Judge 并解析评分结果。"""
        if not task.scoring.judge_rubric:
            return self._error(task, run, "judge_rubric missing")
        if self.config is None:
            return self._error(task, run, "judge execution is not configured")
        if self.config.provider not in {"openai", "anthropic"}:
            return self._error(task, run, f"unsupported judge provider: {self.config.provider}")
        try:
            text = self.call_judge(
                "You are a grading function. Return only valid JSON.",
                self.build_prompt(task, run),
            )
        except Exception as exc:
            return self._error(task, run, str(exc))
        return self.parse_judge_text(task, run, text)

    def call_judge(self, system_prompt: str, user_prompt: str) -> str:
        """调用配置的 Judge API，并返回消息文本。"""
        if self.config is None:
            raise RuntimeError("judge execution is not configured")
        api_key = os.environ.get(self.config.api_key_env)
        if not api_key:
            raise RuntimeError(f"missing API key environment variable: {self.config.api_key_env}")

        if self.config.provider == "anthropic":
            return self._call_anthropic(system_prompt, user_prompt, api_key)
        return self._call_openai(system_prompt, user_prompt, api_key)

    def _call_openai(self, system_prompt: str, user_prompt: str, api_key: str) -> str:
        """调用 OpenAI-compatible chat completions API。"""
        if self.config is None:
            raise RuntimeError("judge execution is not configured")

        response = self._request_with_retry(
            lambda: requests.post(
                f"{self.config.base_url.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.config.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": self.config.temperature,
                    "max_tokens": self.config.max_tokens,
                },
                timeout=self.config.timeout_seconds,
            )
        )
        return str(response.json()["choices"][0]["message"]["content"])

    def _call_anthropic(self, system_prompt: str, user_prompt: str, api_key: str) -> str:
        """调用 Anthropic messages API。"""
        if self.config is None:
            raise RuntimeError("judge execution is not configured")

        response = self._request_with_retry(
            lambda: requests.post(
                f"{self.config.base_url.rstrip('/')}/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.config.model,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": user_prompt}],
                    "temperature": self.config.temperature,
                    "max_tokens": self.config.max_tokens,
                },
                timeout=self.config.timeout_seconds,
            )
        )
        content = response.json()["content"]
        return str(next(item["text"] for item in content if item["type"] == "text"))

    def _request_with_retry(self, request: Callable[[], requests.Response]) -> requests.Response:
        """调用 Judge HTTP 请求，并对临时失败做指数退避重试。"""
        if self.config is None:
            raise RuntimeError("judge execution is not configured")

        max_retries = min(self.config.max_retries, 5)
        for attempt in range(max_retries + 1):
            try:
                response = request()
                response.raise_for_status()
                return response
            except requests.HTTPError as exc:
                if not self._is_retryable_http_error(exc):
                    raise
                if attempt == max_retries:
                    self._raise_retry_exhausted(exc, attempt, max_retries)
            except (requests.ConnectionError, requests.Timeout) as exc:
                if attempt == max_retries:
                    self._raise_retry_exhausted(exc, attempt, max_retries)

            time.sleep(self.config.retry_backoff_seconds * (2**attempt))

        raise RuntimeError("judge request retry loop exited unexpectedly")

    def _raise_retry_exhausted(self, exc: Exception, attempt: int, max_retries: int) -> None:
        """在可重试错误耗尽时补充尝试次数上下文。"""
        attempts = max_retries + 1
        raise RuntimeError(f"judge request failed after {attempts} attempts (max_retries={max_retries}): {exc}") from exc

    def _is_retryable_http_error(self, exc: requests.HTTPError) -> bool:
        """判断 HTTP 错误是否属于 Judge API 可重试状态码。"""
        response = exc.response
        status_code = response.status_code if response is not None else None
        return status_code == 429 or (status_code is not None and 500 <= status_code <= 599)

    def build_prompt(self, task: TaskSpec, run: AgentRunResult) -> str:
        """构造发送给 Judge 的任务、轨迹和工作区上下文。"""
        parts = [
            "You are a grading function. Your ONLY job is to output a single JSON object.",
            "",
            "CRITICAL RULES:",
            "- Do NOT use tools.",
            "- Do NOT write prose outside JSON.",
            "- Respond with ONLY this JSON structure:",
            '{"scores": {"criterion_name": 0.0}, "total": 0.0, "notes": "brief justification"}',
            "",
            "## Task",
            f"Task ID: {task.id}",
            f"Name: {task.name}",
            "",
            task.prompt,
            "",
            "## Grading Rubric",
            task.scoring.judge_rubric or "",
            "",
            "## Execution Status",
            f"Status: {run.status}",
            f"Duration: {run.duration_seconds:.4f}s",
            f"Error: {run.error}" if run.error else "Error: none",
            "",
            "## Agent Transcript Summary",
            self._summarize_trace(run),
            "",
            "## Workspace Files",
            self._read_workspace_files(Path(run.workspace_path)),
        ]
        return self._truncate("\n".join(parts), self._max_context_chars())

    def parse_judge_text(self, task: TaskSpec, run: AgentRunResult, text: str) -> ScoreResult:
        """解析 Judge 返回的 JSON 文本为评分结果。"""
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return self._error(task, run, "judge output is not valid JSON")

        if not isinstance(payload, dict):
            return self._error(task, run, "judge output must be a JSON object")

        total = self._extract_total(payload)
        if total is None or not 0.0 <= total <= 1.0:
            return self._error(task, run, "judge score must be between 0.0 and 1.0")

        breakdown: list[CheckResult] = []
        scores = payload.get("scores")
        if "scores" in payload:
            if not isinstance(scores, dict):
                return self._error(task, run, "judge scores must be an object")
            try:
                parsed_scores = [(str(item_id), self._extract_number(item_score)) for item_id, item_score in scores.items()]
            except (TypeError, ValueError):
                return self._error(task, run, "judge scores must be numeric")
            if any(not 0.0 <= item_score <= 1.0 for _, item_score in parsed_scores):
                return self._error(task, run, "judge scores must be between 0.0 and 1.0")
            breakdown = [
                CheckResult(
                    id=item_id,
                    score=item_score,
                    points=1.0,
                    passed=item_score >= task.pass_threshold,
                    detail="",
                )
                for item_id, item_score in parsed_scores
            ]

        notes = str(payload.get("notes", payload.get("reason", "")))
        return ScoreResult(
            task_id=task.id,
            trial_id=run.trial_id,
            status="scored",
            score=total,
            passed=total >= task.pass_threshold,
            breakdown=breakdown,
            notes=notes,
        )

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

    def _extract_total(self, payload: dict) -> float | None:
        """从推荐或简化 Judge JSON 结构中提取总分。"""
        value = payload.get("total", payload.get("score"))
        try:
            return self._extract_number(value)
        except (TypeError, ValueError):
            return None

    def _extract_number(self, value: object) -> float:
        """从 JSON 数字中提取浮点数，排除 bool 等非评分值。"""
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("judge score must be a number")
        try:
            return float(value)
        except ValueError as exc:
            raise ValueError("judge score must be a number") from exc

    def _truncate(self, value: str, max_chars: int) -> str:
        """按字符数截断文本，并标记被截断的内容。"""
        if max_chars < 0 or len(value) <= max_chars:
            return value
        return f"{value[: max_chars + 1]}...[truncated]"
