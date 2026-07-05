from __future__ import annotations

import json
import os
from typing import Any


class MCPClient:
    """Minimal MCP client for OpenAI-hosted MCP is handled by OpenAI; this is for local HTTP/SSE servers.

    In this repo we expose tools via FastMCP SSE. For local tool calls without OpenAI, we use the existing
    FastAPI /mcp/call endpoint or call tool functions directly.
    """

    def __init__(self, *, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def call_tool(self, *, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        # Local fallback: call the dashboard web endpoint if available.
        import urllib.request

        url = self.base_url + "/mcp/call"
        req = urllib.request.Request(url, method="POST")
        req.add_header("Content-Type", "application/json")
        # Keep required fields stable, but allow passing additional tool-specific args.
        payload: dict[str, Any] = dict(arguments)
        payload["tool"] = name
        payload.setdefault(
            "submission_path",
            arguments.get("submission_path") or arguments.get("submission_file") or arguments.get("submissionPath", ""),
        )
        payload.setdefault("student_name", arguments.get("student_name", ""))
        payload.setdefault("problem_id", arguments.get("problem_id", ""))
        payload.setdefault("language", arguments.get("language", ""))
        payload.setdefault("eval_results", arguments.get("eval_results", {}))
        data = json.dumps(payload).encode("utf-8")
        with urllib.request.urlopen(req, data=data, timeout=30) as resp:
            body = resp.read().decode("utf-8", errors="replace")
        return json.loads(body)


def default_mcp_client() -> MCPClient:
    # Local web app URL
    url = os.getenv("LOCAL_DASHBOARD_URL", "http://127.0.0.1:8080").strip()
    return MCPClient(base_url=url)
