from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from agentbench.core.result import AgentRunResult
from agentbench.core.task import RunConfig, TaskSpec


@dataclass(frozen=True)
class PreflightResult:
    """适配器预检结果。"""

    ok: bool
    message: str = ""


class AgentLoop(Protocol):
    """Agent 适配器需要实现的最小运行协议。"""

    def preflight(self, config: RunConfig) -> PreflightResult:
        """在正式运行前检查外部依赖和配置是否可用。"""
        ...

    def run(
        self,
        task: TaskSpec,
        trial_id: int,
        workspace: Path,
        log_dir: Path,
        timeout_seconds: int,
    ) -> AgentRunResult:
        """在指定工作区执行一个 trial，并返回标准化运行结果。"""
        ...
