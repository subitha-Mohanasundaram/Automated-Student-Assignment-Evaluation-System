"""Post-sandbox script: runs the Explanation Agent on the graded result.

Called by evaluate.yml AFTER the Docker sandbox produces result.json.
Runs on the GitHub Actions runner (has network access) — NOT inside the
--network none sandbox.

Reads:  result.json  +  the student submission file
Writes: result.json  (adds "ai_feedback" block)
        result.txt   (appends AI Feedback section)

Exit codes:
  0  success (or gracefully skipped — e.g. score=100, no key)
  1  hard error (missing files)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Explanation Agent post-evaluation.")
    parser.add_argument("student_file", help="Path to the student submission file")
    parser.add_argument("--result-json", default="result.json", help="Path to result.json")
    parser.add_argument("--result-txt", default="result.txt", help="Path to result.txt")
    parser.add_argument("--problem-id", default=None, help="Problem ID override")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    result_json_path = Path(args.result_json)
    result_txt_path = Path(args.result_txt)
    student_file = Path(args.student_file)

    # --- Guard: require result.json ---
    if not result_json_path.exists():
        print(f"[explain] result.json not found at {result_json_path} — skipping.")
        return 1

    result = json.loads(result_json_path.read_text(encoding="utf-8"))

    # --- Guard: skip if perfect score and no failures ---
    score = float(result.get("score", 0.0))
    case_results = result.get("case_results") or []
    has_failures = any(not c.get("passed", True) for c in case_results)
    passed = int(result.get("passed_cases", 0))
    total = int(result.get("total_test_cases", 0))
    if score >= 100.0 and not has_failures and passed == total and total > 0:
        print("[explain] All tests passed — no explanation needed.")
        _write_perfect_feedback(result_json_path, result_txt_path)
        return 0

    # --- Guard: require Groq API key ---
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        print("[explain] GROQ_API_KEY not set — skipping AI explanation.")
        return 0

    # --- Guard: require student file ---
    if not student_file.exists():
        print(f"[explain] Student file not found: {student_file} — skipping.")
        return 0

    # --- Determine problem_id ---
    problem_id = (args.problem_id or "").strip() or result.get("problem_id", "")
    if not problem_id:
        print("[explain] Could not determine problem_id — skipping.")
        return 0

    student_code = student_file.read_text(encoding="utf-8", errors="replace")

    # --- Build ChromaDB store (fast, ~1s) so retrieval works ---
    try:
        from rag.problem_store import build_store
        build_store()
    except Exception as exc:
        print(f"[explain] ChromaDB build skipped ({exc}); will use direct JSON fallback.")

    # --- Run the CodeMentor ReAct agent ---
    try:
        from agents.codementor_agent import explain_failures
        output = explain_failures(
            problem_id=problem_id,
            student_code=student_code,
            result=result,
            api_key=api_key,
            verbose=False,
        )
    except Exception as exc:
        print(f"[explain] Agent error: {exc} — skipping AI feedback.")
        return 0

    ai_feedback = {
        "explanation": output.explanation,
        "likely_cause": output.likely_cause,
        "hint": output.hint,
        "root_cause": output.root_cause,
        "why_hidden_fail": output.why_hidden_fail,
        "confidence": output.confidence,
        "tools_used": output.tools_used,
        "reasoning_turns": output.reasoning_turns,
    }

    print(f"[explain] Explanation    : {output.explanation}")
    print(f"[explain] Likely cause   : {output.likely_cause}")
    print(f"[explain] Hint           : {output.hint}")
    print(f"[explain] Confidence     : {output.confidence}")
    print(f"[explain] Tools used     : {output.tools_used}")
    print(f"[explain] Reasoning turns: {output.reasoning_turns}")

    # --- Update result.json ---
    result["ai_feedback"] = ai_feedback
    result_json_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"[explain] result.json updated with ai_feedback block.")

    # --- Update result.txt ---
    _append_ai_feedback_to_txt(result_txt_path, ai_feedback)

    return 0


def _write_perfect_feedback(
    result_json_path: Path,
    result_txt_path: Path,
) -> None:
    """Inject a positive ai_feedback block when the submission is perfect."""
    ai_feedback = {
        "explanation": "All test cases passed successfully.",
        "likely_cause": "N/A",
        "hint": "Great work! No issues found.",
    }
    if result_json_path.exists():
        result = json.loads(result_json_path.read_text(encoding="utf-8"))
        result["ai_feedback"] = ai_feedback
        result_json_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    _append_ai_feedback_to_txt(result_txt_path, ai_feedback)


def _append_ai_feedback_to_txt(result_txt_path: Path, ai_feedback: dict) -> None:
    """Append the AI Feedback section to result.txt."""
    section = (
        "\nAI Feedback\n"
        "-----------\n"
        f"Explanation: {ai_feedback['explanation']}\n"
        f"Likely Cause: {ai_feedback['likely_cause']}\n"
        f"Hint: {ai_feedback['hint']}\n"
    )
    if result_txt_path.exists():
        existing = result_txt_path.read_text(encoding="utf-8")
        # Avoid duplicate sections on re-runs.
        if "AI Feedback" not in existing:
            result_txt_path.write_text(existing.rstrip() + "\n" + section, encoding="utf-8")
    else:
        result_txt_path.write_text(section, encoding="utf-8")
    print(f"[explain] result.txt updated with AI Feedback section.")


if __name__ == "__main__":
    raise SystemExit(main())
