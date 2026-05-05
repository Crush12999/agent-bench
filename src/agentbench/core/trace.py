from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


TraceEventType = Literal["assistant_message", "tool_call", "tool_result", "file_event", "error"]


@dataclass(frozen=True)
class TraceEvent:
    """标准化后的执行轨迹事件。"""

    type: TraceEventType
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """转换为可序列化到 JSON 的字典。"""
        return {"type": self.type, "timestamp": self.timestamp, "data": dict(self.data)}


@dataclass(frozen=True)
class Trace:
    """单个 trial 的完整执行轨迹。"""

    events: list[TraceEvent] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """转换为可序列化到 JSON 的字典。"""
        return {"events": [event.to_dict() for event in self.events]}
