from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(slots=True)
class ActionEvent:
    type: str
    timestamp: str
    message: str
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "timestamp": self.timestamp,
            "message": self.message,
            "data": self.data,
        }


def build_event(
    event_type: str, message: str, data: dict[str, Any] | None = None
) -> ActionEvent:
    return ActionEvent(
        type=event_type,
        timestamp=datetime.now(timezone.utc).isoformat(),
        message=message,
        data=data or {},
    )
