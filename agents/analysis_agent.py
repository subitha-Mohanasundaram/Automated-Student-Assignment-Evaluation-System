from __future__ import annotations

from agents.messages import AgentMessage


class AnalysisAgent:
    """Aggregates tool outputs into an analysis block."""

    def analyze(self, *, tool_results: list[dict]) -> AgentMessage:
        by_tool: dict[str, object] = {}
        for item in tool_results:
            key = str(item.get("id") or item.get("name") or "")
            if key:
                by_tool[key] = item.get("result")
        return AgentMessage(role="analysis", type="analysis", payload={"by_tool": by_tool})
