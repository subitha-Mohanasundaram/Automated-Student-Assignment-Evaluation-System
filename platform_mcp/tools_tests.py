from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from assignment_intel.tools import tool_evaluate_submission
from assignment_intel.models import Submission


def evaluate_tests(
    *,
    student_name: str,
    problem_id: str,
    language: str,
    submission_path: str,
    extra_hidden_cases_path: str | None = None,
) -> dict[str, Any]:
    submission = Submission(
        student_name=student_name,
        problem_id=problem_id,
        language=language,
        submission_path=Path(submission_path).resolve(),
        extra_hidden_cases_path=Path(extra_hidden_cases_path).resolve() if extra_hidden_cases_path else None,
    )
    tool_res = tool_evaluate_submission(submission=submission)
    if not tool_res.ok:
        return {"success": False, "score": 0, "error": tool_res.error, "details": tool_res.data or {}}
    details = tool_res.data or {}
    score = details.get("score", 0)
    return {"success": True, "score": score, "details": details}
