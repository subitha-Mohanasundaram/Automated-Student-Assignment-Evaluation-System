from __future__ import annotations

import os
from typing import Any

from agents.messages import AgentMessage


class FeedbackAgent:
    """Generates student-facing feedback and hints."""

    def feedback(self, *, mcp_client: Any, submission: dict[str, Any], analysis: dict[str, Any]) -> AgentMessage:
        # Prefer MCP tool that can use OpenAI optionally.
        args = dict(submission)
        by_tool = analysis.get("by_tool", {}) if isinstance(analysis.get("by_tool"), dict) else {}
        # Prefer expanded eval if present, else base eval.
        eval_block = None
        for key in ("eval_expanded", "eval_base", "evaluate_tests"):
            candidate = by_tool.get(key)
            if isinstance(candidate, dict):
                eval_block = candidate
                break
        if isinstance(eval_block, dict):
            args["eval_results"] = eval_block.get("details", {})
        result = mcp_client.call_tool(name="generate_feedback", arguments=args)
        return AgentMessage(role="feedback", type="feedback", payload={"result": result})
