from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from assignment_intel.models import Submission, ToolResult
from assignment_intel.tool_registry import ToolRegistry
import time


@dataclass
class AgentContext:
    submission: Submission
    tool_results: list[ToolResult]
    artifacts: dict[str, Any]


class PlanningAgent:
    def plan(self, ctx: AgentContext) -> list[str]:
        # Autonomous (rule-based) tool planning.
        # Keeps evaluation deterministic, but adapts tool choices by language and available artifacts.
        plan: list[str] = []

        # Quick guardrail: block obviously unrelated/template submissions.
        plan.append("check_relevance")

        # Always grade first.
        plan.append("evaluate_submission")

        # Complexity runs for all languages; non-Python currently returns "unknown".
        plan.append("analyze_complexity")

        # Feedback is always useful (AI-backed if configured, otherwise rule-based).
        plan.append("ai_feedback")
        return plan


class ExecutionAgent:
    def run(self, registry: ToolRegistry, ctx: AgentContext, tool_name: str) -> None:
        trace = ctx.artifacts.get("agent_trace")
        if not isinstance(trace, list):
            trace = []
            ctx.artifacts["agent_trace"] = trace

        t0 = time.time()
        try:
            if tool_name == "ai_feedback":
                eval_results = ctx.artifacts.get("evaluate_submission", {}) if isinstance(ctx.artifacts.get("evaluate_submission", {}), dict) else {}
                result = registry.call(tool_name, submission=ctx.submission, eval_results=eval_results)
            else:
                result = registry.call(tool_name, submission=ctx.submission)
        except Exception as exc:  # pragma: no cover
            result = ToolResult(tool=tool_name, ok=False, error=str(exc), data={})
        dt_ms = int((time.time() - t0) * 1000)

        trace.append(
            {
                "tool": tool_name,
                "ok": bool(result.ok),
                "error": result.error,
                "duration_ms": dt_ms,
            }
        )
        ctx.tool_results.append(result)
        # Preserve useful tool outputs even on failure for diagnostics.
        if result.data and (result.ok or tool_name in {"check_relevance"}):
            ctx.artifacts[tool_name] = result.data

        if tool_name == "check_relevance" and not result.ok:
            ctx.artifacts["stop_pipeline"] = True


class AnalysisAgent:
    def analyze(self, ctx: AgentContext) -> dict[str, Any]:
        results = ctx.artifacts.get("evaluate_submission", {})
        complexity = ctx.artifacts.get("analyze_complexity", {})
        relevance = ctx.artifacts.get("check_relevance", {})
        return {
            "results": results,
            "complexity": complexity,
            "relevance": relevance,
        }


class FeedbackAgent:
    def generate(self, ctx: AgentContext) -> tuple[str, list[str]]:
        results = ctx.artifacts.get("evaluate_submission", {})
        score = results.get("score", 0)
        passed = results.get("passed_cases", results.get("passed", 0))
        total = results.get("total_test_cases", results.get("total", 0))

        ai = ctx.artifacts.get("ai_feedback", {})
        feedback = str(ai.get("feedback") or f"Score: {score}. Passed {passed}/{total} tests.")
        hints: list[str] = list(ai.get("hints") or [])

        complexity = ctx.artifacts.get("analyze_complexity", {})
        tc = str(complexity.get("time_complexity") or "").strip()
        sc = str(complexity.get("space_complexity") or "").strip()
        if tc and tc.lower() != "unknown":
            hints.append(f"Estimated time complexity: {tc}.")
        if sc and sc.lower() != "unknown":
            hints.append(f"Estimated space complexity: {sc}.")

        plagiarism = results.get("plagiarism", {})
        if isinstance(plagiarism, dict) and plagiarism.get("detected") is True:
            hints.append("Plagiarism risk detected; review your work and cite sources.")

        if passed != total:
            hints.append("Re-check edge cases and input validation; some tests failed.")

        return feedback, hints


class ReportingAgent:
    def build(self, ctx: AgentContext, analysis: dict[str, Any], feedback: str, hints: list[str]) -> dict[str, Any]:
        submission = ctx.submission
        agent_trace = ctx.artifacts.get("agent_trace", [])
        if not isinstance(agent_trace, list):
            agent_trace = []
        plan = ctx.artifacts.get("agent_plan", [])
        if not isinstance(plan, list):
            plan = []
        tool_rows = []
        for r in ctx.tool_results:
            row = {"tool": r.tool, "ok": r.ok, "error": r.error}
            # Include limited debug data for failures (helps diagnose 0-score cases).
            if not r.ok and isinstance(r.data, dict):
                debug = {}
                for k in ("stdout", "stderr", "exit_code", "expected_result_json", "result_file"):
                    if k in r.data:
                        v = r.data.get(k)
                        if isinstance(v, str) and len(v) > 2000:
                            v = v[:2000] + "...(truncated)"
                        debug[k] = v
                if debug:
                    row["debug"] = debug
            tool_rows.append(row)
        return {
            "student_name": submission.student_name,
            "problem_id": submission.problem_id,
            "language": submission.language,
            "submission_path": str(submission.submission_path),
            "submitted_at": submission.submitted_at.isoformat() + "Z",
            "analysis": analysis,
            "feedback": feedback,
            "hints": hints,
            "agent_plan": plan,
            "agent_trace": agent_trace,
            "tools": tool_rows,
        }
