"""
Cost & Runtime Estimator
=========================
Estimates execution cost (USD) and runtime (milliseconds) for a workflow.
Uses known API pricing tables + AI node token estimates + network latency models.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ai_builder.models import EstimateResult, NodeCostEstimate

# ---------------------------------------------------------------------------
# Pricing tables (USD, approximate 2026 figures)
# ---------------------------------------------------------------------------

# OpenAI pricing per 1K tokens
_OPENAI_PRICING = {
    "gpt-4o":        {"input": 0.0025, "output": 0.010},
    "gpt-4o-mini":   {"input": 0.00015,"output": 0.0006},
    "gpt-4-turbo":   {"input": 0.010,  "output": 0.030},
    "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
    "gpt-5":         {"input": 0.005,  "output": 0.020},
}

# Typical API call costs (USD per call)
_API_CALL_COSTS = {
    "google_sheets":   0.00001,
    "gmail":           0.000015,
    "google_drive":    0.00001,
    "slack":           0.0,       # Free
    "github":          0.0,       # Free
    "sendgrid":        0.00006,   # $0.06 per 1K emails
    "smtp":            0.0,
    "openweathermap":  0.0,       # Free tier
    "frankfurter":     0.0,       # Free
    "stripe":          0.0,       # API free, transaction fees separate
    "twilio_sms":      0.0079,    # $0.0079 per SMS
    "aws_lambda":      0.0000002, # $0.20 per 1M invocations
    "rest_api":        0.0,
}

# Typical node runtime in milliseconds (p50 estimates)
_NODE_RUNTIME_MS = {
    "action":         250,
    "webhook":        500,
    "ai":             2500,    # GPT-4o-mini: ~2.5s
    "notification":   200,
    "condition":      5,
    "transform":      2,
    "loop":           10,
    "parallel":       50,     # overhead only
    "human_approval": 0,      # async, not counted in runtime
    "subworkflow":    1000,
}

# AI model average output tokens
_AI_DEFAULT_TOKENS = {
    "input":  500,
    "output": 300,
}


class CostEstimator:
    """Estimates cost and runtime for a workflow without making AI calls."""

    def __init__(self, runs_per_day: int = 100) -> None:
        self.runs_per_day = runs_per_day

    def estimate(
        self,
        workflow_json: Dict[str, Any],
        runs_per_day: Optional[int] = None,
    ) -> EstimateResult:
        """Produce a full cost + runtime estimate."""
        rpd = runs_per_day or self.runs_per_day
        nodes = workflow_json.get("nodes", [])

        node_estimates: List[NodeCostEstimate] = []
        total_cost     = 0.0
        ai_cost        = 0.0
        api_cost       = 0.0

        for node in nodes:
            est = self._estimate_node(node)
            node_estimates.append(est)
            total_cost += est.cost_usd_per_run
            if node.get("type") == "ai":
                ai_cost += est.cost_usd_per_run
            elif node.get("type") in ("action", "webhook", "notification"):
                api_cost += est.cost_usd_per_run

        compute_cost = max(0.0, total_cost - ai_cost - api_cost)

        # Runtime — topological
        total_runtime_ms   = self._estimate_total_runtime(nodes)
        critical_path_ms   = self._estimate_critical_path(nodes)

        assumptions = [
            f"Runs per day: {rpd}",
            "AI nodes use gpt-4o-mini unless specified",
            "Average AI prompt: 500 input tokens, 300 output tokens",
            "Network latency included in node runtimes",
            "Human approval nodes excluded from synchronous runtime",
            "Parallel branches counted as the slowest branch",
        ]

        return EstimateResult(
            success              = True,
            node_estimates       = node_estimates,
            cost_per_run_usd     = total_cost,
            cost_per_day_usd     = total_cost * rpd,
            cost_per_month_usd   = total_cost * rpd * 30,
            estimated_runtime_ms = total_runtime_ms,
            critical_path_ms     = critical_path_ms,
            ai_cost_usd          = ai_cost,
            api_cost_usd         = api_cost,
            compute_cost_usd     = compute_cost,
            runs_per_day         = rpd,
            assumptions          = assumptions,
        )

    def _estimate_node(self, node: Dict) -> NodeCostEstimate:
        node_id   = node.get("id", "unknown")
        node_type = node.get("type", "action")

        cost_usd = 0.0
        notes    = ""

        if node_type == "ai":
            ai_cfg   = node.get("ai", {})
            model    = ai_cfg.get("model", "gpt-4o-mini")
            # Estimate tokens from prompt length
            prompt   = str(ai_cfg.get("prompt", ""))
            in_toks  = max(_AI_DEFAULT_TOKENS["input"],  len(prompt) // 4)
            out_toks = _AI_DEFAULT_TOKENS["output"]
            pricing  = _OPENAI_PRICING.get(model, _OPENAI_PRICING["gpt-4o-mini"])
            cost_usd = (in_toks / 1000 * pricing["input"]) + (out_toks / 1000 * pricing["output"])
            notes    = f"{model}: ~{in_toks} input + {out_toks} output tokens"

        elif node_type == "action":
            action = node.get("action", {})
            integration = action.get("integration", "")
            cost_usd = _API_CALL_COSTS.get(integration, 0.00001)
            notes = f"integration: {integration}"

        elif node_type == "webhook":
            cost_usd = 0.0001   # tiny compute cost
            notes = "outbound HTTP call"

        elif node_type == "notification":
            targets = node.get("notification", {}).get("targets", [])
            for t in targets:
                channel = t.get("channel", "")
                cost_usd += _API_CALL_COSTS.get(channel, 0.00001)
            notes = f"{len(targets)} notification target(s)"

        elif node_type == "parallel":
            # Recurse into branches (guard: sub_node may be a string ID ref)
            branches = node.get("parallel", {}).get("branches", [])
            for branch in branches:
                for sub_node in branch.get("nodes", []):
                    if isinstance(sub_node, dict):
                        sub_est   = self._estimate_node(sub_node)
                        cost_usd += sub_est.cost_usd_per_run
            notes = f"{len(branches)} parallel branches"

        elif node_type == "loop":
            count = node.get("loop", {}).get("count", 10)
            body  = node.get("loop", {}).get("body_nodes", [])
            for sub_node in body:
                if isinstance(sub_node, dict):
                    sub_est   = self._estimate_node(sub_node)
                    cost_usd += sub_est.cost_usd_per_run * count
            notes = f"loop × {count} iterations"

        runtime_ms = _NODE_RUNTIME_MS.get(node_type, 200)
        if node_type == "ai":
            model_factor = {"gpt-4o": 3.0, "gpt-4o-mini": 1.0, "gpt-4-turbo": 2.5}.get(
                node.get("ai", {}).get("model", "gpt-4o-mini"), 1.0
            )
            runtime_ms = int(runtime_ms * model_factor)

        return NodeCostEstimate(
            node_id          = node_id,
            node_type        = node_type,
            cost_usd_per_run = round(cost_usd, 6),
            runtime_ms       = runtime_ms,
            notes            = notes,
        )

    def _estimate_total_runtime(self, nodes: List[Dict]) -> int:
        """Sum all node runtimes (pessimistic sequential estimate)."""
        total = 0
        for node in nodes:
            ntype = node.get("type", "action")
            if ntype == "human_approval":
                continue   # async
            total += _NODE_RUNTIME_MS.get(ntype, 200)
        return total

    def _estimate_critical_path(self, nodes: List[Dict]) -> int:
        """
        Compute the critical path through the DAG.
        Uses longest-path through depends_on chains.
        """
        node_map   = {n.get("id"): n for n in nodes}
        memo:      Dict[str, int] = {}

        def longest_path(nid: str) -> int:
            if nid in memo:
                return memo[nid]
            node  = node_map.get(nid)
            if not node:
                return 0
            ntype = node.get("type", "action")
            own   = _NODE_RUNTIME_MS.get(ntype, 200) if ntype != "human_approval" else 0
            deps  = node.get("depends_on", [])
            if not deps:
                memo[nid] = own
            else:
                memo[nid] = own + max((longest_path(d) for d in deps), default=0)
            return memo[nid]

        if not nodes:
            return 0
        return max((longest_path(n.get("id", "")) for n in nodes), default=0)
