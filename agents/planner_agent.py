from __future__ import annotations

import json
import os
from pathlib import Path
from dataclasses import dataclass
from typing import Any

from agents.messages import AgentMessage


@dataclass(frozen=True)
class Plan:
    tool_calls: list[dict[str, Any]]


class PlannerAgent:
    """Decides which MCP tools to call and with what arguments."""

    def plan(self, *, submission: dict[str, Any]) -> AgentMessage:
        submission = dict(submission)
        submission["submission_path"] = str(Path(str(submission.get("submission_path", ""))).resolve())

        # If OpenAI is configured, ask it to produce a structured tool plan.
        provider = os.getenv("AI_PROVIDER", "null").strip().lower()
        if provider == "openai" and os.getenv("OPENAI_API_KEY"):
            return self._plan_with_openai(submission=submission)

        # Offline autonomous plan with conditions.
        language = str(submission.get("language", "")).strip().lower()
        path = Path(submission["submission_path"])
        source_preview = ""
        try:
            source_preview = path.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")[:500]
        except OSError:
            pass

        tool_calls: list[dict[str, Any]] = []

        if language in {"java", "cpp"}:
            tool_calls.append(
                {
                    "id": "compile",
                    "name": "compile_code",
                    "arguments": {"language": language, "submission_path": submission["submission_path"]},
                }
            )

        # If the file looks suspicious (contains shell-like commands), run_code can capture an immediate error.
        if any(tok in source_preview for tok in ("cd C:\\", "Set-Content", "@\"", "curl.exe", "Invoke-RestMethod")):
            if language in {"python", "javascript"}:
                tool_calls.append(
                    {
                        "id": "smoke_run",
                        "name": "run_code",
                        "arguments": {"language": language, "submission_path": submission["submission_path"], "timeout_s": 5},
                    }
                )

        tool_calls.append({"id": "eval_base", "name": "evaluate_tests", "arguments": submission})

        # If everything passes, optionally expand hidden tests and re-run evaluation (contract-style cases only).
        if language != "python":
            tool_calls.append(
                {
                    "id": "gen_hidden",
                    "name": "generate_hidden_test_expansion",
                    "arguments": {"problem_id": str(submission.get("problem_id") or ""), "count": 10},
                    "when": {"tool": "eval_base", "field": "score", "gte": 90},
                }
            )
            tool_calls.append(
                {
                    "id": "eval_expanded",
                    "name": "evaluate_tests",
                    "arguments": {**submission, "extra_hidden_cases_path": "${gen_hidden.details.path}"},
                    "when": {"tool": "gen_hidden", "field": "details.scorable", "equals": True},
                }
            )

        # Only do heavier analysis if evaluation succeeds.
        tool_calls.append({"id": "complexity", "name": "analyze_complexity", "arguments": submission, "when": {"tool": "eval_base", "field": "success", "equals": True}})
        tool_calls.append({"id": "quality", "name": "code_quality_analysis", "arguments": submission, "when": {"tool": "eval_base", "field": "success", "equals": True}})
        tool_calls.append(
            {
                "id": "plagiarism",
                "name": "detect_plagiarism",
                "arguments": {"submission_path": submission["submission_path"]},
                "when": {"tool": "eval_base", "field": "success", "equals": True},
            }
        )

        return AgentMessage(role="planner", type="plan", payload={"tool_calls": tool_calls})

    def _plan_with_openai(self, *, submission: dict[str, Any]) -> AgentMessage:
        from openai import OpenAI

        model = os.getenv("OPENAI_MODEL", "gpt-5").strip()
        timeout_s = float(os.getenv("OPENAI_TIMEOUT_S", "60"))
        client = OpenAI(timeout=timeout_s, max_retries=int(os.getenv("OPENAI_MAX_RETRIES", "2")))

        system = (
            "You are a planning agent for a code evaluation system.\n"
            "Return ONLY JSON with a key tool_calls which is a list of tool call objects:\n"
            '{"tool_calls":[{"name":"evaluate_tests","arguments":{...}}, ...]}\n'
            "Tools available: run_code, compile_code, evaluate_tests, detect_plagiarism, analyze_complexity, "
            "code_quality_analysis, generate_feedback.\n"
            "Always include evaluate_tests first. Keep calls minimal.\n"
        )
        resp = client.responses.create(
            model=model,
            input=[
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(submission)},
            ],
        )
        text = getattr(resp, "output_text", "") or ""
        try:
            obj = json.loads(text)
            tool_calls = obj.get("tool_calls", [])
            if not isinstance(tool_calls, list):
                tool_calls = []
        except json.JSONDecodeError:
            tool_calls = []

        if not tool_calls:
            tool_calls = [{"name": "evaluate_tests", "arguments": submission}]
        return AgentMessage(role="planner", type="plan", payload={"tool_calls": tool_calls})
