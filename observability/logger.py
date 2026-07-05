from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


LOG_DIR = Path("logs")


def _now_ms() -> int:
    return int(time.time() * 1000)


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2), encoding="utf-8")


def _append_jsonl(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj) + "\n")


def log_tool_call(*, tool: str, arguments: dict[str, Any], result: Any, source: str, run_id: str | None = None) -> None:
    """Lightweight tool-call logging for web + MCP server paths (outside the local multi-agent Trace)."""
    event = {
        "ts_ms": _now_ms(),
        "run_id": run_id,
        "source": source,
        "tool": tool,
        "arguments": arguments,
        "result": result,
    }
    _append_jsonl(LOG_DIR / "tool_calls.jsonl", event)


@dataclass
class Trace:
    run_id: str
    started_ms: int
    agent_messages: list[dict[str, Any]]
    tool_calls: list[dict[str, Any]]
    metrics: dict[str, Any]

    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        self.started_ms = _now_ms()
        self.agent_messages = []
        self.tool_calls = []
        self.metrics = {"run_id": run_id, "started_ms": self.started_ms}

    def add_agent_message(self, msg: dict[str, Any]) -> None:
        self.agent_messages.append({"ts_ms": _now_ms(), **msg})

    def add_tool_call(self, name: str, arguments: dict[str, Any], result: Any) -> None:
        self.tool_calls.append(
            {
                "ts_ms": _now_ms(),
                "run_id": self.run_id,
                "tool": name,
                "arguments": arguments,
                "result": result,
            }
        )

    def set_metric(self, key: str, value: Any) -> None:
        self.metrics[key] = value

    def flush(self) -> None:
        finished_ms = _now_ms()
        self.metrics["finished_ms"] = finished_ms
        self.metrics["duration_ms"] = max(finished_ms - self.started_ms, 0)

        # Latest snapshots
        _write_json(LOG_DIR / "agent_trace.json", {"run_id": self.run_id, "messages": self.agent_messages})
        _write_json(LOG_DIR / "tool_calls.json", {"run_id": self.run_id, "calls": self.tool_calls})
        _write_json(LOG_DIR / "evaluation_metrics.json", self.metrics)

        # History (append)
        _append_jsonl(LOG_DIR / "agent_trace.jsonl", {"run_id": self.run_id, "messages": self.agent_messages})
        _append_jsonl(LOG_DIR / "tool_calls.jsonl", {"run_id": self.run_id, "calls": self.tool_calls})
        _append_jsonl(LOG_DIR / "evaluation_metrics.jsonl", self.metrics)
