"""
CodeMentor Agent — A true ReAct (Reason → Act → Observe → Repeat) agent.

Unlike a single LLM call, this agent:
  1. Receives a goal: "explain why this submission failed"
  2. DECIDES which tools to call based on what it finds
  3. Reads each tool result and decides what to investigate next
  4. Iterates until it has enough evidence to produce a confident explanation
  5. Outputs a structured Pydantic result with audit trail

Tools available (defined in tools_registry.py):
  - get_problem_spec(problem_id)
  - run_visible_tests(code, problem_id, language)
  - analyze_code_structure(code, language)
  - check_error_pattern(error_type, actual, expected)

The agent controls the loop — not your code.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


# ── Output schema ─────────────────────────────────────────────────────────────

class MentorOutput(BaseModel):
    """Structured output from the CodeMentor ReAct Agent."""

    # Core fields (same names as ExplanationOutput for drop-in compatibility)
    explanation: str = Field(
        description="Plain-language explanation of why the submission failed."
    )
    likely_cause: str = Field(
        description="The specific line, operator, or code section that is wrong."
    )
    hint: str = Field(
        description="One actionable hint — guides toward the fix without giving the answer."
    )

    # Extended fields from real agent reasoning
    root_cause: str = Field(
        default="",
        description="Technical root cause identified by the agent through tool use.",
    )
    why_hidden_fail: str = Field(
        default="",
        description="Agent's reasoning about why hidden tests likely also fail.",
    )
    confidence: float = Field(
        default=0.5,
        description="Agent confidence 0.0–1.0 based on evidence gathered.",
    )
    tools_used: list[str] = Field(
        default_factory=list,
        description="Ordered list of tools the agent called during investigation.",
    )
    reasoning_turns: int = Field(
        default=0,
        description="Number of Reason→Act→Observe turns the agent took.",
    )


# ── System prompt ─────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are CodeMentor, an expert AI teaching assistant that investigates \
why a student's coding submission failed.

You have access to 4 tools:
- get_problem_spec: understand what the problem requires
- run_visible_tests: actually execute the student's code and see exact outputs
- analyze_code_structure: inspect the code's AST for structural issues
- check_error_pattern: match failures against known coding mistake patterns

Your investigation strategy:
1. ALWAYS start by calling get_problem_spec to understand the problem
2. THEN call run_visible_tests to see exactly what the code produces
3. THEN call analyze_code_structure to find the structural fault
4. If needed, call check_error_pattern with the first failing case details
5. Once you have enough evidence (usually 3-4 tool calls), stop calling tools
   and produce your final JSON response

Your final response MUST be a JSON object with exactly these keys:
{
  "explanation": "<plain-language explanation of why the submission failed>",
  "likely_cause": "<specific line, operator, or construct that is wrong>",
  "hint": "<ONE actionable hint — do NOT reveal the full solution>",
  "root_cause": "<technical root cause: e.g. 'subtraction operator on line 3'>",
  "why_hidden_fail": "<why hidden tests likely also fail given this root cause>",
  "confidence": <float 0.0-1.0 based on evidence you gathered>
}

Rules:
- Do NOT reveal the correct solution
- Be specific — name the actual line or operator, not generic advice
- confidence should reflect how much evidence you gathered from tools
- If a tool returns an error, note it and continue with other tools
"""


# ── ReAct loop ────────────────────────────────────────────────────────────────

class CodeMentorAgent:
    """ReAct agent that autonomously investigates a failing submission."""

    MAX_TURNS = 6
    MODEL = "llama-3.3-70b-versatile"

    def __init__(self, api_key: str, model: str | None = None, verbose: bool = False) -> None:
        try:
            from groq import Groq
        except ImportError as exc:
            raise ImportError("groq package required: pip install groq") from exc

        self._client = Groq(api_key=api_key)
        self._model = model or os.environ.get("GROQ_MODEL", "").strip() or self.MODEL
        self._verbose = verbose

    def _log(self, msg: str) -> None:
        if self._verbose:
            print(msg, flush=True)

    def run(
        self,
        *,
        problem_id: str,
        student_code: str,
        result: dict[str, Any],
        language: str = "python",
    ) -> MentorOutput:
        """Run the ReAct loop and return a MentorOutput.

        Args:
            problem_id: The problem identifier.
            student_code: Full source code of the student's submission.
            result: The result.json dict from the evaluator.
            language: Programming language of the submission.
        """
        from agents.tools_registry import GROQ_TOOLS, dispatch_tool

        # Build initial context message
        score = float(result.get("score", 0.0))
        passed = int(result.get("passed_cases", 0))
        total = int(result.get("total_test_cases", 0))
        case_results: list[dict] = result.get("case_results") or []
        failing = [c for c in case_results if not c.get("passed", True)]

        # Summarise failures concisely for the initial message
        fail_summary_lines = []
        for c in failing[:4]:
            vis = c.get("visibility", "?")
            err = c.get("error", "wrong_answer")
            inp = c.get("input", "")
            exp = c.get("expected", "")
            act = c.get("actual", "")
            line = f"  [{vis}] error={err}"
            if inp:
                line += f", input={repr(inp[:60])}"
            if exp:
                line += f", expected={repr(exp[:40])}"
            if act:
                line += f", got={repr(act[:40])}"
            fail_summary_lines.append(line)

        fail_summary = (
            "\n".join(fail_summary_lines)
            if fail_summary_lines
            else "  (only hidden tests failed — exact inputs not disclosed)"
        )

        user_message = (
            f"Problem ID: {problem_id}\n"
            f"Language: {language}\n"
            f"Score: {score}%  |  Passed: {passed}/{total}\n\n"
            f"Failing test cases:\n{fail_summary}\n\n"
            f"Student code:\n```{language}\n{student_code[:2500]}\n```\n\n"
            "Investigate why this submission failed and produce your final JSON explanation."
        )

        messages: list[dict] = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]

        tools_used: list[str] = []
        turns = 0

        # ── ReAct loop ────────────────────────────────────────────────────────
        for turn in range(self.MAX_TURNS):
            turns = turn + 1
            self._log(f"\n{_C.YELLOW}[Turn {turns}] Calling Groq...{_C.RESET}")

            response = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                tools=GROQ_TOOLS,
                tool_choice="auto",
                temperature=0.1,
                max_tokens=1024,
                timeout=45,
            )

            choice = response.choices[0]
            finish_reason = choice.finish_reason
            msg = choice.message

            # Add assistant message to history
            messages.append(msg.model_dump(exclude_none=True))

            # ── Agent chose to call tools ────────────────────────────────────
            if finish_reason == "tool_calls" and msg.tool_calls:
                for tc in msg.tool_calls:
                    tool_name = tc.function.name
                    try:
                        tool_args = json.loads(tc.function.arguments or "{}")
                    except json.JSONDecodeError:
                        tool_args = {}

                    tools_used.append(tool_name)
                    self._log(
                        f"{_C.CYAN}  → Agent calls: {tool_name}({_args_summary(tool_args)}){_C.RESET}"
                    )

                    # Execute the tool
                    tool_result = dispatch_tool(tool_name, tool_args)

                    self._log(
                        f"{_C.DIM}    Observed: {_result_summary(tool_result)}{_C.RESET}"
                    )

                    # Feed result back into conversation
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(tool_result, ensure_ascii=False)[:3000],
                    })
                continue  # next turn

            # ── Agent decided it has enough info → final answer ───────────────
            if finish_reason == "stop":
                self._log(
                    f"\n{_C.GREEN}[Turn {turns}] Agent finished — parsing output{_C.RESET}"
                )
                raw_content = msg.content or ""
                return _parse_mentor_output(
                    raw=raw_content,
                    tools_used=tools_used,
                    turns=turns,
                )

            # Unexpected finish reason — treat as done
            self._log(f"[Turn {turns}] Unexpected finish_reason={finish_reason} — stopping")
            break

        # Exceeded MAX_TURNS — parse whatever the last message contained
        last_content = ""
        for m in reversed(messages):
            if m.get("role") == "assistant" and m.get("content"):
                last_content = m["content"]
                break

        return _parse_mentor_output(
            raw=last_content,
            tools_used=tools_used,
            turns=turns,
        )


# ── Output parser ─────────────────────────────────────────────────────────────

def _parse_mentor_output(
    raw: str,
    tools_used: list[str],
    turns: int,
) -> MentorOutput:
    """Parse the agent's final message into a MentorOutput.

    Tolerant: tries JSON first, falls back to section extraction.
    """
    import re

    cleaned = re.sub(r"```(?:json)?", "", raw).replace("```", "").strip()

    # Attempt JSON parse
    try:
        # Find the outermost JSON object
        start = cleaned.find("{")
        end = cleaned.rfind("}") + 1
        if start >= 0 and end > start:
            data = json.loads(cleaned[start:end])
            if isinstance(data, dict):
                return MentorOutput(
                    explanation=str(data.get("explanation", "")).strip() or "See hint below.",
                    likely_cause=str(data.get("likely_cause", "")).strip() or "Review your code.",
                    hint=str(data.get("hint", "")).strip() or "Check edge cases.",
                    root_cause=str(data.get("root_cause", "")).strip(),
                    why_hidden_fail=str(data.get("why_hidden_fail", "")).strip(),
                    confidence=float(data.get("confidence", 0.7)),
                    tools_used=tools_used,
                    reasoning_turns=turns,
                )
    except (json.JSONDecodeError, ValueError):
        pass

    # Fallback: section extraction
    sections: dict[str, str] = {}
    current: str | None = None
    for line in cleaned.splitlines():
        low = line.lower().strip()
        for key in ("explanation", "likely_cause", "hint", "root_cause", "why_hidden_fail"):
            if low.startswith(f'"{key}"') or low.startswith(key + ":"):
                current = key
                val = line.split(":", 1)[1].strip().strip('"').strip(",") if ":" in line else ""
                sections[key] = val
                break
        else:
            if current and line.strip():
                sections[current] = sections.get(current, "") + " " + line.strip()

    return MentorOutput(
        explanation=sections.get("explanation", raw[:300]).strip() or "Review your logic.",
        likely_cause=sections.get("likely_cause", "Check your implementation.").strip(),
        hint=sections.get("hint", "Review edge cases and return values.").strip(),
        root_cause=sections.get("root_cause", "").strip(),
        why_hidden_fail=sections.get("why_hidden_fail", "").strip(),
        confidence=0.5,
        tools_used=tools_used,
        reasoning_turns=turns,
    )


# ── Colour helper (no deps) ───────────────────────────────────────────────────

class _C:
    YELLOW = "\033[93m"
    CYAN   = "\033[96m"
    GREEN  = "\033[92m"
    DIM    = "\033[2m"
    RESET  = "\033[0m"


def _args_summary(args: dict) -> str:
    parts = []
    for k, v in args.items():
        v_str = str(v)
        if len(v_str) > 60:
            v_str = v_str[:57] + "..."
        parts.append(f"{k}={repr(v_str)}")
    return ", ".join(parts)


def _result_summary(result: dict) -> str:
    s = json.dumps(result, ensure_ascii=False)
    return s[:200] + "..." if len(s) > 200 else s


# ── Public API (drop-in for explain_agent.explain_failures) ───────────────────

def explain_failures(
    *,
    problem_id: str,
    student_code: str,
    result: dict[str, Any],
    api_key: str | None = None,
    model: str | None = None,
    verbose: bool = False,
) -> MentorOutput:
    """Drop-in replacement for explain_agent.explain_failures().

    Same signature, richer output — uses the ReAct agent instead of
    a single LLM call.
    """
    key = api_key or os.environ.get("GROQ_API_KEY", "").strip()
    if not key:
        raise ValueError("Groq API key not provided. Set GROQ_API_KEY env var.")

    language = str(result.get("language", "python")).lower()

    agent = CodeMentorAgent(api_key=key, model=model, verbose=verbose)
    return agent.run(
        problem_id=problem_id,
        student_code=student_code,
        result=result,
        language=language,
    )
