from __future__ import annotations

import re
from typing import Any

from agents.messages import AgentMessage


class ExecutionAgent:
    """Calls MCP tools in sequence."""

    _REF_RE = re.compile(r"\$\{([a-zA-Z0-9_\-]+(?:\.[a-zA-Z0-9_\-]+)*)\}")

    def _lookup_ref(self, ref: str, by_id: dict[str, Any]) -> Any:
        parts = [p for p in ref.split(".") if p]
        if not parts:
            return None
        cur: Any = by_id.get(parts[0])
        for key in parts[1:]:
            if isinstance(cur, dict):
                cur = cur.get(key)
            else:
                return None
        return cur

    def _resolve_value(self, value: Any, by_id: dict[str, Any]) -> Any:
        # Dict form: {"$ref": "eval_base.details"}
        if isinstance(value, dict) and isinstance(value.get("$ref"), str):
            return self._lookup_ref(str(value["$ref"]), by_id)
        if isinstance(value, list):
            return [self._resolve_value(v, by_id) for v in value]
        if isinstance(value, dict):
            return {k: self._resolve_value(v, by_id) for k, v in value.items()}
        if isinstance(value, str):
            stripped = value.strip()
            m = self._REF_RE.fullmatch(stripped)
            if m:
                return self._lookup_ref(m.group(1), by_id)

            def _sub(match: re.Match[str]) -> str:
                got = self._lookup_ref(match.group(1), by_id)
                return "" if got is None else str(got)

            return self._REF_RE.sub(_sub, value)
        return value

    def execute(self, *, mcp_client: Any, tool_calls: list[dict[str, Any]]) -> AgentMessage:
        results: list[dict[str, Any]] = []
        by_id: dict[str, Any] = {}
        for call in tool_calls:
            name = str(call.get("name", ""))
            call_id = str(call.get("id") or name)
            args = call.get("arguments") or {}
            if not isinstance(args, dict):
                args = {}
            when = call.get("when")
            if isinstance(when, dict):
                dep_tool = str(when.get("tool", ""))
                field = str(when.get("field", ""))
                ref = dep_tool if not field else f"{dep_tool}.{field}"
                dep_val = self._lookup_ref(ref, by_id)
                if "equals" in when and dep_val != when.get("equals"):
                    results.append(
                        {"id": call_id, "name": name, "skipped": True, "reason": {"when": when}, "result": {"success": True, "details": {"skipped": True}}}
                    )
                    by_id[call_id] = {"success": True, "details": {"skipped": True}}
                    continue
                if "gte" in when:
                    try:
                        if float(dep_val) < float(when.get("gte")):
                            results.append(
                                {"id": call_id, "name": name, "skipped": True, "reason": {"when": when}, "result": {"success": True, "details": {"skipped": True}}}
                            )
                            by_id[call_id] = {"success": True, "details": {"skipped": True}}
                            continue
                    except Exception:
                        results.append(
                            {"id": call_id, "name": name, "skipped": True, "reason": {"when": when}, "result": {"success": True, "details": {"skipped": True}}}
                        )
                        by_id[call_id] = {"success": True, "details": {"skipped": True}}
                        continue
                if "lte" in when:
                    try:
                        if float(dep_val) > float(when.get("lte")):
                            results.append(
                                {"id": call_id, "name": name, "skipped": True, "reason": {"when": when}, "result": {"success": True, "details": {"skipped": True}}}
                            )
                            by_id[call_id] = {"success": True, "details": {"skipped": True}}
                            continue
                    except Exception:
                        results.append(
                            {"id": call_id, "name": name, "skipped": True, "reason": {"when": when}, "result": {"success": True, "details": {"skipped": True}}}
                        )
                        by_id[call_id] = {"success": True, "details": {"skipped": True}}
                        continue
                if "in" in when and isinstance(when.get("in"), list):
                    if dep_val not in when.get("in"):
                        results.append(
                            {"id": call_id, "name": name, "skipped": True, "reason": {"when": when}, "result": {"success": True, "details": {"skipped": True}}}
                        )
                        by_id[call_id] = {"success": True, "details": {"skipped": True}}
                        continue

            resolved_args = self._resolve_value(args, by_id)
            if not isinstance(resolved_args, dict):
                resolved_args = {}

            res = mcp_client.call_tool(name=name, arguments=resolved_args)
            if isinstance(res, dict):
                by_id[call_id] = res
            results.append({"id": call_id, "name": name, "arguments": resolved_args, "result": res})
        return AgentMessage(role="executor", type="tool_results", payload={"results": results})
