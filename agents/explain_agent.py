"""Explanation Agent — generates root-cause feedback for failing test cases.

Calls the Groq API (LLaMA 3.3-70B) with problem context retrieved via RAG.
Produces a structured Pydantic output: explanation, likely_cause, hint.

Example standalone usage:
    python agents/explain_agent.py \\
        --problem-id two_sum \\
        --student-code examples/two_sum_cheat.py \\
        --result-json result.json
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

try:
    from pydantic import BaseModel, Field
except ImportError as exc:  # pragma: no cover
    raise ImportError("pydantic is required: pip install pydantic") from exc


# ---------------------------------------------------------------------------
# Pydantic output schema
# ---------------------------------------------------------------------------

class ExplanationOutput(BaseModel):
    """Structured AI feedback for a failing submission."""

    explanation: str = Field(
        description="Plain-language explanation of why the submission failed."
    )
    likely_cause: str = Field(
        description="The most likely faulty section or line(s) in the student's code."
    )
    hint: str = Field(
        description="A single actionable hint that guides the student toward the fix "
                    "without revealing the full solution."
    )


# ---------------------------------------------------------------------------
# Groq provider
# ---------------------------------------------------------------------------

class GroqExplainProvider:
    """Calls Groq's chat completions endpoint using the groq SDK."""

    DEFAULT_MODEL = "llama-3.3-70b-versatile"

    def __init__(self, api_key: str, model: str | None = None) -> None:
        try:
            from groq import Groq  # type: ignore
        except ImportError as exc:
            raise ImportError("groq package is required: pip install groq") from exc

        self._client = Groq(api_key=api_key)
        self._model = model or self.DEFAULT_MODEL

    def generate(self, *, system_prompt: str, user_prompt: str) -> ExplanationOutput:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=512,
            timeout=30,
        )
        raw_content = response.choices[0].message.content or ""
        return _parse_output(raw_content)


# ---------------------------------------------------------------------------
# Output parsing (tolerant JSON extraction with plain-text fallback)
# ---------------------------------------------------------------------------

def _parse_output(raw: str) -> ExplanationOutput:
    """Parse the LLM response into an ExplanationOutput.

    Tries JSON first (the prompt requests JSON), then falls back to
    heuristic section extraction so a malformed response still returns
    something useful instead of raising.
    """
    import re

    # Strip markdown code fences if present.
    cleaned = re.sub(r"```(?:json)?", "", raw).replace("```", "").strip()

    # Attempt JSON parse.
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return ExplanationOutput(
                explanation=str(data.get("explanation", "")).strip() or "See hint below.",
                likely_cause=str(data.get("likely_cause", "")).strip() or "Unknown section.",
                hint=str(data.get("hint", "")).strip() or "Review your logic.",
            )
    except (json.JSONDecodeError, ValueError):
        pass

    # Plain-text fallback: split on labelled sections.
    sections: dict[str, str] = {}
    current_key: str | None = None
    for line in cleaned.splitlines():
        lower = line.lower().strip()
        if lower.startswith("explanation:"):
            current_key = "explanation"
            sections[current_key] = line.split(":", 1)[1].strip()
        elif lower.startswith("likely cause:") or lower.startswith("likely_cause:"):
            current_key = "likely_cause"
            sections[current_key] = line.split(":", 1)[1].strip()
        elif lower.startswith("hint:"):
            current_key = "hint"
            sections[current_key] = line.split(":", 1)[1].strip()
        elif current_key and line.strip():
            sections[current_key] = sections.get(current_key, "") + " " + line.strip()

    return ExplanationOutput(
        explanation=sections.get("explanation", raw[:300]).strip() or "See hint.",
        likely_cause=sections.get("likely_cause", "Review your submission.").strip(),
        hint=sections.get("hint", "Check edge cases and return values.").strip(),
    )


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """You are a teaching assistant reviewing a student's failing coding submission.
Your goal is to explain WHY the submission failed in plain language, identify the likely faulty section,
and provide ONE actionable hint — but do NOT reveal the complete solution.

Respond with a JSON object containing exactly these keys:
{
  "explanation": "<plain-language explanation of the failure>",
  "likely_cause": "<specific function name, loop, or code section that is likely wrong>",
  "hint": "<one concrete hint that guides toward the fix without giving away the answer>"
}
Do not include anything outside the JSON object."""


def _build_user_prompt(
    *,
    problem_context: str,
    student_code: str,
    failing_tests: list[dict[str, Any]],
    score: float,
    passed: int,
    total: int,
) -> str:
    # Summarise failing test details concisely (avoid bloating context window).
    fail_lines: list[str] = []
    for tc in failing_tests[:5]:  # cap at 5 cases
        vis = tc.get("visibility", "?")
        err = tc.get("error", "wrong_answer")
        inp = tc.get("input", "")
        expected = tc.get("expected", "")
        actual = tc.get("actual", "")
        line = f"  [{vis}] error={err}"
        if inp:
            line += f", input={repr(inp[:80])}"
        if expected:
            line += f", expected={repr(expected[:80])}"
        if actual:
            line += f", got={repr(actual[:80])}"
        fail_lines.append(line)

    fail_summary = "\n".join(fail_lines) if fail_lines else "  (hidden test cases failed — inputs not disclosed)"
    code_snippet = student_code[:2000] if len(student_code) > 2000 else student_code

    return (
        f"--- Problem Context ---\n{problem_context}\n\n"
        f"--- Score Summary ---\n"
        f"Score: {score}%  |  Passed: {passed}/{total}\n\n"
        f"--- Failing Test Cases ---\n{fail_summary}\n\n"
        f"--- Student Code ---\n```\n{code_snippet}\n```\n\n"
        "Explain the failure, identify the likely faulty section, and give one hint."
    )


# ---------------------------------------------------------------------------
# Main agent function
# ---------------------------------------------------------------------------

def explain_failures(
    *,
    problem_id: str,
    student_code: str,
    result: dict[str, Any],
    api_key: str | None = None,
    model: str | None = None,
) -> ExplanationOutput:
    """Generate an AI explanation for a failing submission.

    Args:
        problem_id: The problem being evaluated.
        student_code: The full source code of the student's submission.
        result: The result.json payload (dict).
        api_key: Groq API key (falls back to GROQ_API_KEY env var).
        model: Groq model name (falls back to GROQ_MODEL env var, then default).

    Returns:
        ExplanationOutput with explanation, likely_cause, and hint.
    """
    from rag.retrieve import get_problem_context

    key = api_key or os.environ.get("GROQ_API_KEY", "").strip()
    if not key:
        raise ValueError(
            "Groq API key not provided. Set GROQ_API_KEY env var or pass api_key=..."
        )

    resolved_model = model or os.environ.get("GROQ_MODEL", "").strip() or None
    provider = GroqExplainProvider(api_key=key, model=resolved_model)

    # Retrieve problem context from RAG layer.
    problem_context = get_problem_context(problem_id)

    # Extract failing test cases from result payload.
    case_results: list[dict[str, Any]] = result.get("case_results") or []
    failing_tests = [c for c in case_results if not c.get("passed", True)]

    score = float(result.get("score", 0.0))
    passed = int(result.get("passed_cases", 0))
    total = int(result.get("total_test_cases", 0))

    user_prompt = _build_user_prompt(
        problem_context=problem_context,
        student_code=student_code,
        failing_tests=failing_tests,
        score=score,
        passed=passed,
        total=total,
    )

    return provider.generate(system_prompt=_SYSTEM_PROMPT, user_prompt=user_prompt)


# ---------------------------------------------------------------------------
# CLI entrypoint (for standalone testing)
# ---------------------------------------------------------------------------

def _cli() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Run the Explanation Agent on a result.json.")
    parser.add_argument("--problem-id", required=True, help="Problem ID (e.g. two_sum)")
    parser.add_argument("--student-code", required=True, help="Path to the student's source file")
    parser.add_argument("--result-json", default="result.json", help="Path to result.json")
    parser.add_argument("--model", default=None, help="Groq model override")
    args = parser.parse_args()

    code_path = Path(args.student_code)
    if not code_path.exists():
        print(f"Error: student code file not found: {code_path}", file=sys.stderr)
        return 1

    result_path = Path(args.result_json)
    if not result_path.exists():
        print(f"Error: result.json not found: {result_path}", file=sys.stderr)
        return 1

    result_data = json.loads(result_path.read_text(encoding="utf-8"))
    score = float(result_data.get("score", 0.0))

    if score >= 100.0 and not any(
        not c.get("passed", True) for c in (result_data.get("case_results") or [])
    ):
        print("Submission passed all tests — no explanation needed.")
        return 0

    student_code = code_path.read_text(encoding="utf-8", errors="replace")

    output = explain_failures(
        problem_id=args.problem_id,
        student_code=student_code,
        result=result_data,
        model=args.model,
    )

    print("\n=== Explanation Agent Output ===")
    print(f"Explanation : {output.explanation}")
    print(f"Likely Cause: {output.likely_cause}")
    print(f"Hint        : {output.hint}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
