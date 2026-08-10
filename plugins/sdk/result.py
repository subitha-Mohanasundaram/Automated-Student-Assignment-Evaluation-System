"""Plugin result types."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional


@dataclass
class ActionResult:
    """Returned by every plugin action execution."""
    success:   bool
    data:      Dict[str, Any] = field(default_factory=dict)
    error:     Optional[str]  = None
    metadata:  Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime       = field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def ok(cls, data: Optional[Dict[str, Any]] = None, **kw: Any) -> "ActionResult":
        return cls(success=True, data=data or {}, **kw)

    @classmethod
    def fail(cls, error: str, **kw: Any) -> "ActionResult":
        return cls(success=False, error=error, **kw)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success":   self.success,
            "data":      self.data,
            "error":     self.error,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class TriggerEvent:
    """An event emitted by a plugin trigger."""
    trigger_id: str
    plugin_id:  str
    payload:    Dict[str, Any] = field(default_factory=dict)
    timestamp:  datetime       = field(default_factory=lambda: datetime.now(timezone.utc))
    dedup_key:  Optional[str]  = None
    metadata:   Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trigger_id": self.trigger_id,
            "plugin_id":  self.plugin_id,
            "payload":    self.payload,
            "timestamp":  self.timestamp.isoformat(),
            "dedup_key":  self.dedup_key,
        }
