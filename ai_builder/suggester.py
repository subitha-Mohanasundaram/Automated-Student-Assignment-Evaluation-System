"""
Improvement Suggester
=====================
Generates AI-powered improvement suggestions and optimization proposals
for an existing workflow, with before/after cost estimates.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from ai_builder.ai_client import AIClient
from ai_builder.estimator import CostEstimator
from ai_builder.models import (
    EstimateResult, OptimizationResult, Suggestion, SuggestionResult,
)

_SYSTEM = """\
You are a workflow automation expert and architect. Analyze the workflow and
suggest specific, actionable improvements. Return JSON only.
"""


class ImprovementSuggester:
    """Generates improvement suggestions with cost/time impact estimates."""

    def __init__(self, client: AIClient, estimator: CostEstimator) -> None:
        self._ai        = client
        self._estimator = estimator

    def suggest(self, workflow_json: Dict[str, Any]) -> SuggestionResult:
        """Generate improvement suggestions for a workflow."""
        try:
            # Get AI suggestions
            suggestions = self._ai_suggest(workflow_json)

            # Add deterministic suggestions
            suggestions.extend(self._deterministic_suggest(workflow_json))

            # Build optimizations with before/after estimates
            before_estimate = self._estimator.estimate(workflow_json)
            optimizations   = self._build_optimizations(suggestions, before_estimate)

            summary = self._build_summary(suggestions)

            return SuggestionResult(
                success       = True,
                suggestions   = suggestions,
                optimizations = optimizations,
                summary       = summary,
            )
        except Exception as exc:
            return SuggestionResult(success=False, error=str(exc))

    # ------------------------------------------------------------------
    # AI suggestions
    # ------------------------------------------------------------------

    def _ai_suggest(self, wf: Dict) -> List[Suggestion]:
        compact = {
            "name":    wf.get("name"),
            "nodes": [{
                "id":   n.get("id"),
                "name": n.get("name"),
                "type": n.get("type"),
                "has_retry":   bool(n.get("retry")),
                "has_timeout": bool(n.get("timeout")),
                "depends_on":  n.get("depends_on", []),
            } for n in wf.get("nodes", [])]
        }
        messages = [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": f"""Analyze this workflow and return 5–8 specific improvement suggestions.

Return JSON:
{{
  "suggestions": [
    {{
      "category": "performance|reliability|cost|security|ux",
      "priority": "high|medium|low",
      "title": "Short title",
      "description": "What to improve and why",
      "action": "Natural language edit command (e.g. 'Add retry to fetch_data node')",
      "estimated_impact": "e.g. '40% faster', '$0.002 savings per run'",
      "auto_applicable": true|false
    }}
  ]
}}

Workflow:
{json.dumps(compact, indent=2)}"""},
        ]
        try:
            result = self._ai.chat_json(messages, max_tokens=1500)
            return [
                Suggestion(
                    category        = s.get("category", "ux"),
                    priority        = s.get("priority", "medium"),
                    title           = s.get("title", ""),
                    description     = s.get("description", ""),
                    action          = s.get("action", ""),
                    estimated_impact= s.get("estimated_impact", ""),
                    auto_applicable = s.get("auto_applicable", False),
                )
                for s in result.get("suggestions", [])
            ]
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Deterministic suggestions
    # ------------------------------------------------------------------

    def _deterministic_suggest(self, wf: Dict) -> List[Suggestion]:
        suggestions: List[Suggestion] = []
        nodes = wf.get("nodes", [])

        # Sequential AI calls → parallel
        ai_nodes = [n for n in nodes if n.get("type") == "ai"]
        if len(ai_nodes) >= 2:
            # Check if any two AI nodes are independent (no shared dependency path)
            independent_pairs = []
            for i in range(len(ai_nodes)):
                for j in range(i + 1, len(ai_nodes)):
                    ni, nj = ai_nodes[i], ai_nodes[j]
                    # Simple check: if neither depends on the other
                    if ni.get("id") not in nj.get("depends_on", []) and nj.get("id") not in ni.get("depends_on", []):
                        independent_pairs.append((ni.get("id"), nj.get("id")))
            if independent_pairs:
                pair = independent_pairs[0]
                suggestions.append(Suggestion(
                    category         = "performance",
                    priority         = "high",
                    title            = "Parallelize Independent AI Nodes",
                    description      = f"Nodes '{pair[0]}' and '{pair[1]}' are independent AI calls that run sequentially. Running them in parallel could halve their combined latency.",
                    action           = f"Wrap {pair[0]} and {pair[1]} in a parallel block",
                    estimated_impact = f"~{2500 * (len(independent_pairs))}ms faster per run",
                    auto_applicable  = True,
                ))

        # No error handler on critical nodes
        critical_types = ("action", "ai", "webhook")
        no_handler = [n for n in nodes if n.get("type") in critical_types and not n.get("error_handler")]
        if no_handler:
            suggestions.append(Suggestion(
                category         = "reliability",
                priority         = "high",
                title            = "Add Error Handlers to Critical Nodes",
                description      = f"{len(no_handler)} nodes make external calls without error handlers. A single failure will stop the entire workflow.",
                action           = f"Add error_handler with on_error: 'continue' to {', '.join(n.get('id','') for n in no_handler[:3])}",
                estimated_impact = "Prevents workflow failures from transient API errors",
                auto_applicable  = True,
            ))

        # Missing variables declaration
        import re
        wf_str = json.dumps(wf)
        var_refs = set(re.findall(r"\{\{([a-zA-Z_][a-zA-Z0-9_.]*)\}}", wf_str))
        declared = {v.get("name") for v in wf.get("variables", [])}
        undeclared = [v for v in var_refs if v not in declared and not v.startswith("$")]
        if undeclared:
            suggestions.append(Suggestion(
                category         = "reliability",
                priority         = "medium",
                title            = "Declare Missing Variables",
                description      = f"Found {len(undeclared)} variable references without declarations: {', '.join(list(undeclared)[:5])}",
                action           = "Add variable declarations with types and defaults to the variables section",
                estimated_impact = "Prevents runtime errors from undefined variables",
                auto_applicable  = False,
            ))

        # Long workflow with no notifications
        notification_nodes = [n for n in nodes if n.get("type") == "notification"]
        if len(nodes) > 5 and not notification_nodes:
            suggestions.append(Suggestion(
                category         = "ux",
                priority         = "low",
                title            = "Add Completion Notification",
                description      = "This workflow has no notification nodes. Users won't know when it completes or fails.",
                action           = "Add a Slack or email notification at the end of the workflow",
                estimated_impact = "Better user experience and observability",
                auto_applicable  = True,
            ))

        return suggestions

    def _build_optimizations(self, suggestions: List[Suggestion], before: EstimateResult) -> List[OptimizationResult]:
        """Pair high-priority suggestions with estimated savings."""
        optimizations = []
        for s in suggestions:
            if s.priority == "high":
                # Estimate rough savings
                savings_pct = 0.0
                if s.category == "performance":
                    savings_pct = 30.0
                elif s.category == "cost":
                    savings_pct = 20.0
                elif s.category == "reliability":
                    savings_pct = 0.0   # reliability doesn't reduce cost but reduces failure rate
                optimizations.append(OptimizationResult(
                    suggestion      = s,
                    before_estimate = before,
                    savings_pct     = savings_pct,
                ))
        return optimizations

    def _build_summary(self, suggestions: List[Suggestion]) -> str:
        if not suggestions:
            return "✨ Workflow looks well-optimized! No major improvements found."
        high   = [s for s in suggestions if s.priority == "high"]
        medium = [s for s in suggestions if s.priority == "medium"]
        parts  = []
        if high:   parts.append(f"🔴 {len(high)} high-priority improvement(s)")
        if medium: parts.append(f"🟡 {len(medium)} medium-priority suggestion(s)")
        total  = len(suggestions)
        return f"Found {total} suggestion(s): " + " · ".join(parts)
