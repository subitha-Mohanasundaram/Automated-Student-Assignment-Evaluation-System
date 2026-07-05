from __future__ import annotations

from pathlib import Path
from typing import Any

from assignment_intel.ai_provider import get_ai_provider
from assignment_intel.code_review import review_python_file
from assignment_intel.models import Submission, ToolResult


def _basic_hints_from_results(results: dict[str, Any]) -> list[str]:
    hints: list[str] = []
    total = results.get("total_test_cases", results.get("total", 0)) or 0
    passed = results.get("passed_cases", results.get("passed", 0)) or 0
    if total and passed < total:
        hints.append("Some tests failed: check edge cases, types, and return values.")
    if results.get("anti_cheat", {}).get("passed") is False:
        hints.append("Anti-cheat failed: remove disallowed imports/calls and re-submit.")
    plagiarism = results.get("plagiarism", {})
    if isinstance(plagiarism, dict) and plagiarism.get("detected") is True:
        hints.append("Plagiarism risk detected: write your own solution and cite sources.")
    return hints


def tool_ai_feedback(*, submission: Submission, eval_results: dict[str, Any] | None = None) -> ToolResult:
    eval_results = eval_results or {}
    hints = _basic_hints_from_results(eval_results)

    review: list[dict[str, str]] = []
    if submission.language.lower() == "python":
        for f in review_python_file(Path(submission.submission_path)):
            review.append({"level": f.level, "message": f.message})

    prompt = (
        "You are a teaching assistant. Provide short feedback and hints without revealing the full answer.\n"
        f"Problem: {submission.problem_id}\n"
        f"Language: {submission.language}\n"
        f"Score: {eval_results.get('score', 0)}\n"
        f"Passed/Total: {eval_results.get('passed_cases', 0)}/{eval_results.get('total_test_cases', 0)}\n"
        f"Review findings: {review}\n"
    )
    provider = get_ai_provider()
    ai = provider.generate(prompt=prompt)

    merged_hints = list(dict.fromkeys([*hints, *ai.hints]))  # stable unique
    return ToolResult(
        tool="ai_feedback",
        ok=True,
        data={
            "feedback": ai.feedback,
            "hints": merged_hints,
            "review": review,
        },
    )

