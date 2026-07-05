from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AgentConfig:
    model: str
    mcp_server_url: str
    mcp_server_label: str = "assignment-intel-local"


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing environment variable: {name}")
    return value


def load_agent_config() -> AgentConfig:
    # NOTE: OpenAI cannot reach localhost; provide a publicly reachable URL (ngrok/cloudflared).
    model = os.getenv("OPENAI_MODEL", "gpt-5").strip()
    mcp_url = _require_env("MCP_SERVER_URL")
    label = os.getenv("MCP_SERVER_LABEL", "assignment-intel").strip() or "assignment-intel"
    return AgentConfig(model=model, mcp_server_url=mcp_url, mcp_server_label=label)


def _get_timeout_s() -> float:
    raw = os.getenv("OPENAI_TIMEOUT_S", "60").strip()
    try:
        return float(raw)
    except ValueError:
        return 60.0


def _get_max_retries() -> int:
    raw = os.getenv("OPENAI_MAX_RETRIES", "2").strip()
    try:
        return int(raw)
    except ValueError:
        return 2


def run_openai_agent(
    *,
    student_name: str,
    problem_id: str,
    language: str,
    submission_path: Path,
) -> dict[str, Any]:
    from openai import OpenAI
    from openai import APITimeoutError

    cfg = load_agent_config()
    client = OpenAI(timeout=_get_timeout_s(), max_retries=_get_max_retries())

    submission_path = submission_path.resolve()
    instruction = (
        "You are a multi-agent grading system. Simulate these agents and communicate ONLY via structured JSON messages:\n"
        "- PlannerAgent: decides which tools to call\n"
        "- ExecutionAgent: calls MCP tools\n"
        "- AnalysisAgent: analyzes results (complexity, plagiarism, quality)\n"
        "- FeedbackAgent: generates student-facing feedback and hints\n"
        "- ReportingAgent: produces final report\n"
        "\n"
        "Tools available via MCP:\n"
        "- run_code\n"
        "- compile_code\n"
        "- evaluate_tests\n"
        "- detect_plagiarism\n"
        "- analyze_complexity\n"
        "- code_quality_analysis\n"
        "- generate_feedback\n"
        "\n"
        "Process:\n"
        "1) PlannerAgent outputs a plan (list of tool calls).\n"
        "2) ExecutionAgent executes the plan using MCP tools.\n"
        "3) AnalysisAgent summarizes tool outputs.\n"
        "4) FeedbackAgent calls generate_feedback (pass eval_results from evaluate_tests.details).\n"
        "5) ReportingAgent returns FINAL JSON.\n"
        "\n"
        "FINAL OUTPUT MUST BE JSON ONLY with keys:\n"
        "{\n"
        '  "agents": [ { "role": "...", "type": "...", "payload": {...} }, ... ],\n'
        '  "final_report": { "score": number, "results": {...}, "plagiarism": {...}, "complexity": {...}, "quality": {...}, "feedback": string, "hints": [..] }\n'
        "}\n"
        "Do not reveal full solutions; provide hints only.\n"
    )

    user_payload = {
        "student_name": student_name,
        "problem_id": problem_id,
        "language": language,
        "submission_path": str(submission_path),
    }

    try:
        resp = client.responses.create(
            model=cfg.model,
            input=[
                {"role": "system", "content": instruction},
                {"role": "user", "content": f"Submission:\n{user_payload}"},
            ],
            tools=[
                {
                    "type": "mcp",
                    "server_label": cfg.mcp_server_label,
                    "server_url": cfg.mcp_server_url,
                    "require_approval": "never",
                }
            ],
        )
    except APITimeoutError as exc:
        return {
            "ok": False,
            "error": "openai_timeout",
            "detail": str(exc),
            "hint": "Set OPENAI_TIMEOUT_S=120 and retry. Also confirm api.openai.com:443 is reachable.",
        }

    def _extract_text(r: Any) -> str:
        text_val = getattr(r, "output_text", None)
        if isinstance(text_val, str) and text_val.strip():
            return text_val.strip()
        if hasattr(r, "output"):
            parts: list[str] = []
            for item in r.output:  # type: ignore[attr-defined]
                if isinstance(item, dict) and item.get("type") == "output_text":
                    parts.append(str(item.get("text", "")))
            return "\n".join(parts).strip()
        return ""

    def _coerce(obj: Any) -> dict[str, Any]:
        if not isinstance(obj, dict):
            return {"agents": [], "final_report": {"score": 0, "results": {}, "plagiarism": {}, "complexity": {}, "quality": {}, "feedback": "", "hints": []}}
        agents = obj.get("agents")
        if not isinstance(agents, list):
            agents = []
        final_report = obj.get("final_report")
        if not isinstance(final_report, dict):
            final_report = {}
        final_report.setdefault("score", 0)
        final_report.setdefault("results", {})
        final_report.setdefault("plagiarism", {})
        final_report.setdefault("complexity", {})
        final_report.setdefault("quality", {})
        final_report.setdefault("feedback", "")
        final_report.setdefault("hints", [])
        if not isinstance(final_report.get("hints"), list):
            final_report["hints"] = []
        return {"agents": agents, "final_report": final_report}

    def _repair_json(bad_text: str) -> dict[str, Any]:
        # Second pass: no tool calls, just repair into the expected schema.
        repair_system = (
            "Return ONLY valid JSON matching this schema:\n"
            '{ "agents": [ { "role": string, "type": string, "payload": object } ],'
            '  "final_report": { "score": number, "results": object, "plagiarism": object, "complexity": object,'
            '  "quality": object, "feedback": string, "hints": array } }'
        )
        r2 = client.responses.create(
            model=cfg.model,
            input=[
                {"role": "system", "content": repair_system},
                {"role": "user", "content": bad_text},
            ],
        )
        t2 = _extract_text(r2)
        import json as _json

        try:
            return _coerce(_json.loads(t2))
        except Exception:
            return _coerce({})

    text = _extract_text(resp)
    if not text and hasattr(resp, "output"):
        # Fallback: scan output for text blocks
        parts = []
        for item in resp.output:  # type: ignore[attr-defined]
            if isinstance(item, dict) and item.get("type") == "output_text":
                parts.append(str(item.get("text", "")))
        text = "\n".join(parts)

    if not text:
        return {"ok": False, "error": "no_output_text", "raw": getattr(resp, "model_dump", lambda: {})()}

    # Expect JSON in the final response.
    import json

    try:
        return {"ok": True, "agent_report": _coerce(json.loads(text))}
    except json.JSONDecodeError:
        return {"ok": True, "agent_report": _repair_json(text), "agent_text": text}
