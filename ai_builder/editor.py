"""
Natural Language Editor
=======================
Interprets natural language edit commands and applies them to workflow JSON.

Examples:
  "Move Email before Slack"
  "Replace Gmail with Outlook"
  "Add retry to fetch_data node"
  "Add a 30-second delay after send_notification"
  "Wrap ai_analysis and ai_summary in parallel"
  "Add a condition: if status is 'error' skip to error_handler"
  "Set timeout on process_data to 60 seconds"
  "Rename extract_data to parse_response"
"""
from __future__ import annotations

import copy
import json
import uuid
from typing import Any, Dict, List, Optional, Tuple

from ai_builder.ai_client import AIClient
from ai_builder.models import EditResult


_PARSE_SYSTEM = """\
You are a workflow JSON editor assistant. Parse the user's natural language
edit command into a structured JSON action. Return JSON only.
"""

_APPLY_SYSTEM = """\
You are a workflow JSON editor. Apply the given edit operation to the workflow JSON.
Return the complete modified workflow JSON. No explanation. JSON only.
"""


class NLEditor:
    """Applies natural language edit commands to workflow JSON."""

    def __init__(self, client: AIClient) -> None:
        self._ai = client

    def edit(self, workflow_json: Dict[str, Any], command: str) -> EditResult:
        """Apply a natural language edit command to the workflow."""
        original = copy.deepcopy(workflow_json)
        try:
            # Step 1: Parse command into structured action
            parsed = self._parse_command(workflow_json, command)

            # Step 2: Try deterministic apply first
            updated, changes = self._deterministic_apply(workflow_json, parsed)

            if updated is None:
                # Step 3: Fall back to AI-powered edit
                updated, changes = self._ai_apply(original, command, parsed)

            if updated is None:
                return EditResult(
                    success           = False,
                    original_workflow = original,
                    command_parsed    = parsed.get("command"),
                    error             = "Could not apply edit command. Please be more specific.",
                )

            diff_summary = self._build_diff_summary(original, updated)
            return EditResult(
                success           = True,
                original_workflow = original,
                updated_workflow  = updated,
                command_parsed    = f"{parsed.get('command')} ({parsed.get('explanation', '')})",
                changes           = changes,
                diff_summary      = diff_summary,
            )

        except Exception as exc:
            return EditResult(
                success           = False,
                original_workflow = original,
                error             = str(exc),
            )

    # ------------------------------------------------------------------
    # Parse command
    # ------------------------------------------------------------------

    def _parse_command(self, wf: Dict, command: str) -> Dict[str, Any]:
        """Parse NL command into a structured action dict."""
        node_ids   = [n.get("id") for n in wf.get("nodes", [])]
        node_names = [n.get("name") for n in wf.get("nodes", [])]

        messages = [
            {"role": "system", "content": _PARSE_SYSTEM + """
Parse the user's edit command into this JSON structure:
{
  "command": "move_node|replace_plugin|add_node|remove_node|add_retry|add_condition|add_parallel|add_delay|set_timeout|rename_node|connect_nodes|update_params|wrap_in_loop|enable_node|disable_node|set_variable|add_error_handler",
  "args": { "command-specific args" },
  "explanation": "one sentence explaining what will change",
  "confidence": 0.0-1.0
}

Command args by type:
- move_node: {"node_id": "...", "before": "target_node_id"} or {"after": "target_node_id"}
- replace_plugin: {"node_id": "..." or null, "old_integration": "...", "new_integration": "...", "old_operation": "...", "new_operation": "..."}
- add_node: {"node_type": "action|condition|ai|notification|delay|webhook", "name": "...", "after": "node_id", "params": {...}}
- remove_node: {"node_id": "..."}
- add_retry: {"node_id": "...", "max_attempts": 3, "backoff": "exponential"}
- add_delay: {"after_node_id": "...", "duration_seconds": 30}
- set_timeout: {"node_id": "...", "duration_seconds": 60}
- rename_node: {"node_id": "...", "new_name": "..."}
- add_parallel: {"node_ids": ["...", "..."]}
- add_condition: {"after_node_id": "...", "expression": "...", "if_branch": "node_id", "else_branch": "node_id"}
- add_error_handler: {"node_id": "...", "on_error": "continue|retry|abort", "fallback": "node_id or null"}
"""},
            {"role": "user", "content": f"""Available nodes: {node_ids}
Node names: {node_names}

Edit command: {command}"""},
        ]
        try:
            return self._ai.chat_json(messages, max_tokens=400)
        except Exception:
            return {"command": "unknown", "args": {}, "explanation": command, "confidence": 0.3}

    # ------------------------------------------------------------------
    # Deterministic apply
    # ------------------------------------------------------------------

    def _deterministic_apply(
        self, wf: Dict, parsed: Dict
    ) -> Tuple[Optional[Dict], List[str]]:
        """Apply well-understood commands without AI."""
        cmd  = parsed.get("command")
        args = parsed.get("args", {})
        wf   = copy.deepcopy(wf)

        if cmd == "add_retry":
            return self._apply_add_retry(wf, args)
        elif cmd == "set_timeout":
            return self._apply_set_timeout(wf, args)
        elif cmd == "rename_node":
            return self._apply_rename(wf, args)
        elif cmd == "add_delay":
            return self._apply_add_delay(wf, args)
        elif cmd == "add_error_handler":
            return self._apply_add_error_handler(wf, args)
        elif cmd == "remove_node":
            return self._apply_remove_node(wf, args)

        return None, []

    def _apply_add_retry(self, wf: Dict, args: Dict) -> Tuple[Optional[Dict], List[str]]:
        node_id = args.get("node_id")
        changes = []
        for node in wf.get("nodes", []):
            if node.get("id") == node_id or (not node_id and node.get("type") in ("action", "ai", "webhook")):
                node["retry"] = {
                    "max_attempts":    args.get("max_attempts", 3),
                    "backoff_strategy":args.get("backoff", "exponential"),
                    "initial_delay":   "PT1S",
                    "max_delay":       "PT30S",
                }
                changes.append(f"Added retry (max {args.get('max_attempts', 3)} attempts) to '{node.get('id')}'")
                if node_id:
                    break   # only target node if specific
        return (wf, changes) if changes else (None, [])

    def _apply_set_timeout(self, wf: Dict, args: Dict) -> Tuple[Optional[Dict], List[str]]:
        node_id = args.get("node_id")
        secs    = int(args.get("duration_seconds", 30))
        changes = []
        for node in wf.get("nodes", []):
            if node.get("id") == node_id:
                node["timeout"] = {"duration": f"PT{secs}S"}
                changes.append(f"Set timeout on '{node_id}' to {secs}s")
                break
        return (wf, changes) if changes else (None, [])

    def _apply_rename(self, wf: Dict, args: Dict) -> Tuple[Optional[Dict], List[str]]:
        node_id  = args.get("node_id")
        new_name = args.get("new_name")
        if not new_name:
            return None, []
        changes = []
        for node in wf.get("nodes", []):
            if node.get("id") == node_id:
                old_name = node.get("name", node_id)
                node["name"] = new_name
                changes.append(f"Renamed '{old_name}' → '{new_name}'")
                break
        return (wf, changes) if changes else (None, [])

    def _apply_add_delay(self, wf: Dict, args: Dict) -> Tuple[Optional[Dict], List[str]]:
        after_id = args.get("after_node_id")
        secs     = int(args.get("duration_seconds", 30))
        delay_id = f"delay_{uuid.uuid4().hex[:6]}"
        nodes    = wf.get("nodes", [])

        # Find insertion point
        for i, node in enumerate(nodes):
            if node.get("id") == after_id:
                delay_node = {
                    "id":         delay_id,
                    "name":       f"Wait {secs}s",
                    "type":       "delay",
                    "description":f"Wait {secs} seconds before proceeding",
                    "depends_on": [after_id],
                    "delay":      {"duration": f"PT{secs}S"},
                }
                # Update all nodes that depended on after_id to now depend on delay
                for other_node in nodes:
                    if after_id in other_node.get("depends_on", []):
                        deps = [d if d != after_id else delay_id for d in other_node["depends_on"]]
                        other_node["depends_on"] = deps
                nodes.insert(i + 1, delay_node)
                return wf, [f"Inserted {secs}s delay after '{after_id}'"]
        return None, []

    def _apply_add_error_handler(self, wf: Dict, args: Dict) -> Tuple[Optional[Dict], List[str]]:
        node_id  = args.get("node_id")
        on_error = args.get("on_error", "continue")
        fallback = args.get("fallback")
        changes  = []
        for node in wf.get("nodes", []):
            if node.get("id") == node_id:
                node["error_handler"] = {
                    "on_error":          on_error,
                    "fallback_node_id":  fallback,
                    "notify_on_failure": True,
                }
                changes.append(f"Added error handler (on_error='{on_error}') to '{node_id}'")
                break
        return (wf, changes) if changes else (None, [])

    def _apply_remove_node(self, wf: Dict, args: Dict) -> Tuple[Optional[Dict], List[str]]:
        node_id = args.get("node_id")
        nodes   = wf.get("nodes", [])
        before  = len(nodes)
        wf["nodes"] = [n for n in nodes if n.get("id") != node_id]
        # Remove dangling depends_on references
        for node in wf["nodes"]:
            node["depends_on"] = [d for d in node.get("depends_on", []) if d != node_id]
        after = len(wf["nodes"])
        if after < before:
            return wf, [f"Removed node '{node_id}'"]
        return None, []

    # ------------------------------------------------------------------
    # AI-powered apply (fallback)
    # ------------------------------------------------------------------

    def _ai_apply(
        self, original: Dict, command: str, parsed: Dict
    ) -> Tuple[Optional[Dict], List[str]]:
        """Use AI to apply complex edits (move, replace plugin, add parallel)."""
        messages = [
            {"role": "system", "content": _APPLY_SYSTEM},
            {"role": "user", "content": f"""Apply this edit to the workflow JSON.

EDIT COMMAND: {command}
PARSED INTENT: {json.dumps(parsed, indent=2)}

CURRENT WORKFLOW:
{json.dumps(original, indent=2)}

Return ONLY the complete modified workflow JSON. No markdown. No explanation."""},
        ]
        try:
            raw     = self._ai.chat(messages, response_format="json", max_tokens=5000)
            updated = json.loads(raw)
            changes = [parsed.get("explanation", command)]
            return updated, changes
        except Exception:
            return None, []

    # ------------------------------------------------------------------
    # Diff summary
    # ------------------------------------------------------------------

    def _build_diff_summary(self, original: Dict, updated: Dict) -> str:
        orig_nodes   = {n.get("id") for n in original.get("nodes", [])}
        upd_nodes    = {n.get("id") for n in updated.get("nodes", [])}
        added        = upd_nodes - orig_nodes
        removed      = orig_nodes - upd_nodes
        lines        = []
        if added:   lines.append(f"+ Added nodes: {', '.join(added)}")
        if removed: lines.append(f"- Removed nodes: {', '.join(removed)}")
        orig_cnt = len(original.get("nodes", []))
        upd_cnt  = len(updated.get("nodes", []))
        if orig_cnt != upd_cnt:
            lines.append(f"~ Node count: {orig_cnt} → {upd_cnt}")
        if not lines:
            lines.append("~ Modified existing node(s)")
        return "\n".join(lines)
