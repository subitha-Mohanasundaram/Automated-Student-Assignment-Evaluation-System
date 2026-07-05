from __future__ import annotations

import json
from pathlib import Path
from typing import Any
import uuid

from agents.analysis_agent import AnalysisAgent
from agents.execution_agent import ExecutionAgent
from agents.feedback_agent import FeedbackAgent
from agents.planner_agent import PlannerAgent
from agents.reporting_agent import ReportingAgent
from evaluation.mcp_client import default_mcp_client
from observability.logger import Trace


def run_local_multi_agent(*, submission: dict[str, Any]) -> dict[str, Any]:
    """Runs the multi-agent pipeline locally (no OpenAI) by calling local dashboard MCP endpoints."""
    planner = PlannerAgent()
    executor = ExecutionAgent()
    analyzer = AnalysisAgent()
    feedback = FeedbackAgent()
    reporter = ReportingAgent()

    trace = Trace(run_id=str(uuid.uuid4()))
    trace.set_metric("mode", "local_multi_agent")
    trace.set_metric("submission", submission)

    plan_msg = planner.plan(submission=submission)
    trace.add_agent_message(plan_msg.to_dict())
    tool_calls = plan_msg.payload.get("tool_calls", [])
    if not isinstance(tool_calls, list):
        tool_calls = []

    client = default_mcp_client()
    exec_msg = executor.execute(mcp_client=client, tool_calls=tool_calls)
    trace.add_agent_message(exec_msg.to_dict())
    results = exec_msg.payload.get("results", [])
    if not isinstance(results, list):
        results = []

    for item in results:
        name = str(item.get("name", ""))
        trace.add_tool_call(name=name, arguments=item.get("arguments", {}) if isinstance(item.get("arguments"), dict) else {}, result=item.get("result"))

    analysis_msg = analyzer.analyze(tool_results=results)
    trace.add_agent_message(analysis_msg.to_dict())
    feedback_msg = feedback.feedback(mcp_client=client, submission=submission, analysis=analysis_msg.payload)
    trace.add_agent_message(feedback_msg.to_dict())
    report_msg = reporter.report(
        submission=submission,
        plan_msg=plan_msg,
        exec_msg=exec_msg,
        analysis_msg=analysis_msg,
        feedback_msg=feedback_msg,
    )
    trace.add_agent_message(report_msg.to_dict())
    trace.set_metric("score", report_msg.payload.get("score", 0))
    trace.flush()
    return report_msg.payload


def save_report(report: dict[str, Any], out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return out_path
