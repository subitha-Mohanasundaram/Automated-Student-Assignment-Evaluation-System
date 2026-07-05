from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from agents.messages import AgentMessage


class ReportingAgent:
    """Builds the final evaluation report JSON."""

    def report(
        self,
        *,
        submission: dict[str, Any],
        plan_msg: AgentMessage,
        exec_msg: AgentMessage,
        analysis_msg: AgentMessage,
        feedback_msg: AgentMessage,
    ) -> AgentMessage:
        report: dict[str, Any] = {
            "submitted_at": datetime.now(timezone.utc).isoformat(),
            "submission": submission,
            "planner": plan_msg.to_dict(),
            "execution": exec_msg.to_dict(),
            "analysis": analysis_msg.to_dict(),
            "feedback": feedback_msg.to_dict(),
        }
        # Surface score if available
        try:
            results = exec_msg.payload.get("results", [])
            for item in results:
                item_id = item.get("id") or item.get("name")
                if item_id in {"eval_expanded", "eval_base", "evaluate_tests"} and item.get("name") == "evaluate_tests":
                    res = item.get("result", {})
                    if isinstance(res, dict) and "score" in res:
                        report["score"] = res.get("score")
                        # Prefer the first score we see for eval_expanded, otherwise keep going.
                        if item_id == "eval_expanded":
                            break
        except Exception:
            pass
        return AgentMessage(role="reporting", type="final_report", payload=report)
