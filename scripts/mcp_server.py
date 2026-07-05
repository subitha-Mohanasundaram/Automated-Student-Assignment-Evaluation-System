from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from assignment_intel.models import Submission
from assignment_intel.orchestrator import build_default_registry


SERVER_INFO = {"name": "assignment-intel-mcp", "version": "0.1"}


def _tool_specs() -> list[dict[str, Any]]:
    return [
        {
            "name": "evaluate_submission",
            "description": "Run grading evaluation for a submission using the configured sandbox mode.",
            "inputSchema": {
                "type": "object",
                "required": ["student_name", "problem_id", "language", "submission_path"],
                "properties": {
                    "student_name": {"type": "string"},
                    "problem_id": {"type": "string"},
                    "language": {"type": "string", "enum": ["python", "java", "javascript", "cpp"]},
                    "submission_path": {"type": "string"},
                },
            },
        },
        {
            "name": "analyze_complexity",
            "description": "Estimate time/space complexity for a submission (Python heuristic).",
            "inputSchema": {
                "type": "object",
                "required": ["student_name", "problem_id", "language", "submission_path"],
                "properties": {
                    "student_name": {"type": "string"},
                    "problem_id": {"type": "string"},
                    "language": {"type": "string"},
                    "submission_path": {"type": "string"},
                },
            },
        },
        {
            "name": "ai_feedback",
            "description": "Generate feedback/hints (offline by default; pluggable provider).",
            "inputSchema": {
                "type": "object",
                "required": ["student_name", "problem_id", "language", "submission_path"],
                "properties": {
                    "student_name": {"type": "string"},
                    "problem_id": {"type": "string"},
                    "language": {"type": "string"},
                    "submission_path": {"type": "string"},
                    "eval_results": {"type": "object"},
                },
            },
        },
    ]


def _make_submission(params: dict[str, Any]) -> Submission:
    submission_path = Path(str(params["submission_path"])).resolve()
    return Submission(
        student_name=str(params["student_name"]),
        submission_path=submission_path,
        problem_id=str(params["problem_id"]),
        language=str(params["language"]),
    )


def _handle_initialize(msg_id: Any) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": msg_id,
        "result": {
            "serverInfo": SERVER_INFO,
            "capabilities": {"tools": {}},
        },
    }


def _handle_tools_list(msg_id: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": _tool_specs()}}


def _handle_tools_call(msg_id: Any, params: dict[str, Any]) -> dict[str, Any]:
    name = str(params.get("name") or "")
    arguments = params.get("arguments") or {}
    if not isinstance(arguments, dict):
        return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32602, "message": "arguments must be an object"}}

    registry = build_default_registry()
    submission = _make_submission(arguments)
    if name == "ai_feedback":
        eval_results = arguments.get("eval_results") if isinstance(arguments.get("eval_results"), dict) else {}
        result = registry.call(name, submission=submission, eval_results=eval_results)
    else:
        result = registry.call(name, submission=submission)

    return {"jsonrpc": "2.0", "id": msg_id, "result": asdict(result)}


def _handle(msg: dict[str, Any]) -> dict[str, Any] | None:
    if msg.get("jsonrpc") != "2.0":
        return None
    method = msg.get("method")
    msg_id = msg.get("id")

    # Notifications have no id; ignore.
    if msg_id is None:
        return None

    if method == "initialize":
        return _handle_initialize(msg_id)
    if method == "tools/list":
        return _handle_tools_list(msg_id)
    if method == "tools/call":
        params = msg.get("params") or {}
        if not isinstance(params, dict):
            return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32602, "message": "params must be an object"}}
        return _handle_tools_call(msg_id, params)

    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32601, "message": f"Unknown method: {method}"}}


def main() -> int:
    for line in sys.stdin:
        raw = line.strip()
        if not raw:
            continue
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(msg, dict):
            continue
        resp = _handle(msg)
        if resp is None:
            continue
        sys.stdout.write(json.dumps(resp) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

