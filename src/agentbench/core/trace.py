from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


TraceEventType = Literal["assistant_message", "tool_call", "tool_result", "file_event", "error"]


@dataclass(frozen=True)
class TraceEvent:
    type: TraceEventType
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "timestamp": self.timestamp, "data": dict(self.data)}


@dataclass(frozen=True)
class Trace:
    events: list[TraceEvent] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"events": [event.to_dict() for event in self.events]}
