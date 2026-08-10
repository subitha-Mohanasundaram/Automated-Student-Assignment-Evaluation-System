"""
Workflow Explainer
==================
Explains a workflow JSON in plain English at multiple levels of detail.
- Summary: 2–3 sentences
- Step-by-step: numbered list
- Node-level: per-node purpose, inputs, outputs
- Data flow: how data travels through the workflow
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from ai_builder.ai_client import AIClient
from ai_builder.models import ExplainResult, NodeExplanation

_SYSTEM = """\
You are an expert at explaining technical workflow automations to non-technical users.
Use simple, clear language. Avoid jargon. Always respond in JSON.
"""


class WorkflowExplainer:
    """Produces plain-English explanations of workflow JSON documents."""

    def __init__(self, client: AIClient) -> None:
        self._ai = client

    def explain(self, workflow_json: Dict[str, Any]) -> ExplainResult:
        """Generate a full explanation of a workflow."""
        try:
            # Compact representation for the AI
            compact = self._compact(workflow_json)

            messages = [
                {"role": "system", "content": _SYSTEM},
                {"role": "user",   "content": f"""Explain this workflow. Return JSON with:
{{
  "summary": "2-3 sentence overview for non-technical users",
  "steps": ["numbered plain-English step descriptions"],
  "data_flow": "how data moves through the workflow",
  "prerequisites": ["what needs to be configured/available before running"],
  "node_details": [
    {{
      "node_id": "...",
      "node_type": "...",
      "plain": "one sentence plain description",
      "purpose": "why this node exists in the workflow",
      "inputs": ["variable names or data it receives"],
      "outputs": ["variable names or data it produces"]
    }}
  ]
}}

Workflow:
{json.dumps(compact, indent=2)}"""},
            ]
            result = self._ai.chat_json(messages, max_tokens=2000)
            node_details = [
                NodeExplanation(
                    node_id   = n.get("node_id", ""),
                    node_type = n.get("node_type", ""),
                    plain     = n.get("plain", ""),
                    purpose   = n.get("purpose", ""),
                    inputs    = n.get("inputs", []),
                    outputs   = n.get("outputs", []),
                )
                for n in result.get("node_details", [])
            ]
            return ExplainResult(
                success      = True,
                summary      = result.get("summary", ""),
                steps        = result.get("steps", []),
                node_details = node_details,
                data_flow    = result.get("data_flow", ""),
                prerequisites= result.get("prerequisites", []),
            )
        except Exception as exc:
            return ExplainResult(success=False, error=str(exc))

    def explain_node(self, node: Dict[str, Any], context: Dict[str, Any]) -> str:
        """Explain a single node in one sentence."""
        messages = [
            {"role": "system", "content": "Explain this workflow node in one plain sentence for a non-technical user."},
            {"role": "user",   "content": f"Node: {json.dumps(node)}\nWorkflow name: {context.get('name', 'unknown')}"},
        ]
        try:
            return self._ai.chat(messages, max_tokens=100).strip()
        except Exception:
            return f"{node.get('type', 'unknown')} node: {node.get('name', '')}"

    @staticmethod
    def _compact(workflow_json: Dict) -> Dict:
        """Produce a compact, token-efficient representation."""
        return {
            "workflow_id": workflow_json.get("workflow_id"),
            "name":        workflow_json.get("name"),
            "description": workflow_json.get("description"),
            "triggers": [
                {"id": t.get("id"), "type": t.get("type")}
                for t in workflow_json.get("triggers", [])
            ],
            "nodes": [
                {
                    "id":         n.get("id"),
                    "name":       n.get("name"),
                    "type":       n.get("type"),
                    "depends_on": n.get("depends_on", []),
                    "description":n.get("description", ""),
                }
                for n in workflow_json.get("nodes", [])
            ],
        }
