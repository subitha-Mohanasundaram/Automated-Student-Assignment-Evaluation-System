from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from assignment_intel.agents import AnalysisAgent, AgentContext, ExecutionAgent, FeedbackAgent, PlanningAgent, ReportingAgent
from assignment_intel.models import EvaluationReport, Submission
from assignment_intel.tool_registry import ToolRegistry
from assignment_intel.tool_registry import Tool
from assignment_intel.tools import tool_ai_feedback_wrapper, tool_analyze_complexity, tool_check_relevance, tool_evaluate_submission


def run_pipeline(registry: ToolRegistry, submission: Submission) -> EvaluationReport:
    ctx = AgentContext(submission=submission, tool_results=[], artifacts={})

    planner = PlanningAgent()
    executor = ExecutionAgent()
    analyzer = AnalysisAgent()
    feedback_agent = FeedbackAgent()
    reporter = ReportingAgent()

    plan = planner.plan(ctx)
    ctx.artifacts["agent_plan"] = list(plan)
    for tool_name in plan:
        executor.run(registry, ctx, tool_name)
        if ctx.artifacts.get("stop_pipeline") is True:
            break

    analysis: dict[str, Any] = analyzer.analyze(ctx)
    feedback, hints = feedback_agent.generate(ctx)

    report_dict = reporter.build(ctx, analysis=analysis, feedback=feedback, hints=hints)
    return EvaluationReport(submission=submission, results=report_dict, tool_results=ctx.tool_results, feedback=feedback, hints=hints)


def save_report(report: EvaluationReport, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.results, indent=2), encoding="utf-8")
    return output_path


def build_default_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(Tool(name="check_relevance", fn=tool_check_relevance))
    registry.register(Tool(name="evaluate_submission", fn=tool_evaluate_submission))
    registry.register(Tool(name="analyze_complexity", fn=tool_analyze_complexity))
    registry.register(Tool(name="ai_feedback", fn=tool_ai_feedback_wrapper))
    return registry
