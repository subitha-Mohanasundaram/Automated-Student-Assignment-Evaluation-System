from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from assignment_intel.models import Submission, ToolResult
from assignment_intel.orchestrator import build_default_registry


@dataclass(frozen=True)
class ToolCall:
    tool: str
    submission_path: str
    student_name: str
    problem_id: str
    language: str


def call_tool(req: ToolCall) -> dict[str, Any]:
    submission_path = Path(req.submission_path).resolve()
    submission = Submission(
        student_name=req.student_name,
        submission_path=submission_path,
        problem_id=req.problem_id,
        language=req.language,
    )
    registry = build_default_registry()
    result: ToolResult = registry.call(req.tool, submission=submission)
    return asdict(result)

