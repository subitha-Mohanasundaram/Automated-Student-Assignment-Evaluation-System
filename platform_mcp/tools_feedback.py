from __future__ import annotations

from typing import Any

from assignment_intel.ai_feedback import tool_ai_feedback
from assignment_intel.models import Submission


def generate_feedback(
    *,
    student_name: str,
    problem_id: str,
    language: str,
    submission_path: str,
    eval_results: dict | None = None,
) -> dict[str, Any]:
    submission = Submission(
        student_name=student_name,
        problem_id=problem_id,
        language=language,
        submission_path=submission_path,
    )
    res = tool_ai_feedback(submission=submission, eval_results=eval_results or {})
    return {"success": res.ok, "details": res.data or {}, "error": res.error}

