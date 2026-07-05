from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Submission:
    student_name: str
    submission_path: Path
    problem_id: str
    language: str
    extra_hidden_cases_path: Path | None = None
    submitted_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ToolResult:
    tool: str
    ok: bool
    data: dict[str, Any] | None = None
    error: str | None = None


@dataclass
class EvaluationReport:
    submission: Submission
    results: dict[str, Any]
    tool_results: list[ToolResult]
    feedback: str
    hints: list[str]
