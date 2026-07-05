from __future__ import annotations

from pathlib import Path
from typing import Any

from assignment_intel.complexity import estimate_python_complexity
from assignment_intel.code_review import review_python_file


def analyze_complexity(*, language: str, submission_path: str) -> dict[str, Any]:
    lang = language.strip().lower()
    path = Path(submission_path).resolve()
    if not path.exists():
        return {"success": False, "error": "file_not_found", "details": {"path": str(path)}}
    if lang != "python":
        return {"success": True, "details": {"time_complexity": "unknown", "space_complexity": "unknown", "notes": ["heuristic only for python"]}}
    est = estimate_python_complexity(path)
    return {"success": True, "details": {"time_complexity": est.time_complexity, "space_complexity": est.space_complexity, "notes": est.notes}}


def code_quality_analysis(*, language: str, submission_path: str) -> dict[str, Any]:
    lang = language.strip().lower()
    path = Path(submission_path).resolve()
    if not path.exists():
        return {"success": False, "error": "file_not_found", "details": {"path": str(path)}}
    if lang == "python":
        findings = [{"level": f.level, "message": f.message} for f in review_python_file(path)]
        return {"success": True, "details": {"findings": findings}}
    # Simple placeholders for other languages
    return {"success": True, "details": {"findings": [{"level": "info", "message": "Quality analysis not implemented for this language yet."}]}}

