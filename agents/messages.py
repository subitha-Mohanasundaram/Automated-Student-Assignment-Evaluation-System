from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


Role = Literal["planner", "executor", "analysis", "feedback", "reporting"]


@dataclass(frozen=True)
class AgentMessage:
    role: Role
    type: str
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"role": self.role, "type": self.type, "payload": self.payload}

