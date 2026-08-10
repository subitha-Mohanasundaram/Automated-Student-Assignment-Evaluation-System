"""
Mistake Detector
================
Detects structural, logical, and best-practice issues in workflow JSON.
Uses a combination of deterministic rules + AI reasoning.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Set

from ai_builder.ai_client import AIClient
from ai_builder.models import DiagnoseResult, WorkflowIssue


class MistakeDetector:
    """
    Two-layer detection:
    1. Deterministic rules (fast, no API cost)
    2. AI reasoning for logical / semantic issues
    """

    def __init__(self, client: AIClient) -> None:
        self._ai = client

    def detect(self, workflow_json: Dict[str, Any]) -> DiagnoseResult:
        """Run all checks and return a DiagnoseResult."""
        issues: List[WorkflowIssue] = []

        # Layer 1: deterministic rule checks
        issues.extend(self._check_structure(workflow_json))
        issues.extend(self._check_dag(workflow_json))
        issues.extend(self._check_reliability(workflow_json))
        issues.extend(self._check_security(workflow_json))
        issues.extend(self._check_performance(workflow_json))

        # Layer 2: AI semantic analysis
        ai_issues = self._ai_semantic_check(workflow_json)
        issues.extend(ai_issues)

        # Deduplicate by code + node_id
        seen: Set[str] = set()
        unique: List[WorkflowIssue] = []
        for issue in issues:
            key = f"{issue.code}:{issue.node_id}"
            if key not in seen:
                seen.add(key)
                unique.append(issue)

        summary = self._generate_summary(unique)
        return DiagnoseResult(
            success = True,
            issues  = unique,
            summary = summary,
        )

    # ------------------------------------------------------------------
    # Layer 1: Deterministic rules
    # ------------------------------------------------------------------

    def _check_structure(self, wf: Dict) -> List[WorkflowIssue]:
        issues = []
        required = ["workflow_id", "name", "version", "nodes", "triggers"]
        for field in required:
            if not wf.get(field):
                issues.append(WorkflowIssue(
                    severity = "error",
                    code     = "MISSING_FIELD",
                    node_id  = None,
                    message  = f"Missing required field: '{field}'",
                    suggestion = f"Add the '{field}' field to the workflow root.",
                    auto_fixable = False,
                ))

        if not wf.get("nodes"):
            issues.append(WorkflowIssue(
                severity = "error",
                code     = "EMPTY_WORKFLOW",
                node_id  = None,
                message  = "Workflow has no nodes defined.",
                suggestion = "Add at least one action, condition, or notification node.",
            ))
            return issues

        # Check node IDs are unique
        node_ids = [n.get("id") for n in wf.get("nodes", [])]
        seen_ids: Set[str] = set()
        for nid in node_ids:
            if nid in seen_ids:
                issues.append(WorkflowIssue(
                    severity  = "error",
                    code      = "DUPLICATE_NODE_ID",
                    node_id   = nid,
                    message   = f"Duplicate node ID: '{nid}'",
                    suggestion = f"Rename one of the nodes with ID '{nid}' to a unique value.",
                    auto_fixable = True,
                ))
            if nid:
                seen_ids.add(nid)

        # Check node names exist
        for node in wf.get("nodes", []):
            if not node.get("name"):
                issues.append(WorkflowIssue(
                    severity  = "warning",
                    code      = "MISSING_NODE_NAME",
                    node_id   = node.get("id"),
                    message   = f"Node '{node.get('id')}' has no name.",
                    suggestion = "Add a descriptive 'name' field to this node.",
                    auto_fixable = True,
                ))

        return issues

    def _check_dag(self, wf: Dict) -> List[WorkflowIssue]:
        issues = []
        node_ids = {n.get("id") for n in wf.get("nodes", [])}

        # Check depends_on references valid nodes
        for node in wf.get("nodes", []):
            for dep in node.get("depends_on", []):
                if dep not in node_ids:
                    issues.append(WorkflowIssue(
                        severity  = "error",
                        code      = "INVALID_DEPENDENCY",
                        node_id   = node.get("id"),
                        message   = f"Node '{node.get('id')}' depends on unknown node '{dep}'.",
                        suggestion = f"Fix the depends_on reference to an existing node ID, or create a node with ID '{dep}'.",
                        auto_fixable = False,
                    ))

        # Detect cycles using DFS
        adj: Dict[str, List[str]] = {n.get("id"): n.get("depends_on", []) for n in wf.get("nodes", [])}
        visited:  Set[str] = set()
        rec_stack: Set[str] = set()

        def dfs(node: str) -> bool:
            visited.add(node)
            rec_stack.add(node)
            for dep in adj.get(node, []):
                if dep not in visited:
                    if dfs(dep):
                        return True
                elif dep in rec_stack:
                    return True
            rec_stack.discard(node)
            return False

        for nid in list(node_ids):
            if nid and nid not in visited:
                if dfs(nid):
                    issues.append(WorkflowIssue(
                        severity  = "error",
                        code      = "CIRCULAR_DEPENDENCY",
                        node_id   = nid,
                        message   = "Circular dependency detected in the workflow DAG.",
                        suggestion = "Remove the circular depends_on reference. A node cannot depend on its own downstream nodes.",
                    ))
                    break

        # Check for disconnected nodes (no path from trigger nodes)
        trigger_nodes = [n.get("id") for n in wf.get("nodes", []) if not n.get("depends_on")]
        reachable: Set[str] = set(trigger_nodes)
        changed = True
        while changed:
            changed = False
            for node in wf.get("nodes", []):
                nid = node.get("id")
                if nid not in reachable and all(dep in reachable for dep in node.get("depends_on", [])):
                    reachable.add(nid)
                    changed = True

        for nid in node_ids:
            if nid and nid not in reachable:
                issues.append(WorkflowIssue(
                    severity  = "warning",
                    code      = "UNREACHABLE_NODE",
                    node_id   = nid,
                    message   = f"Node '{nid}' is unreachable (no path from any start node).",
                    suggestion = "Connect this node by adding it to another node's depends_on, or remove it.",
                    auto_fixable = False,
                ))

        return issues

    def _check_reliability(self, wf: Dict) -> List[WorkflowIssue]:
        issues = []
        for node in wf.get("nodes", []):
            nid       = node.get("id")
            node_type = node.get("type")

            # External API calls should have retry
            if node_type in ("action", "webhook", "ai") and not node.get("retry"):
                issues.append(WorkflowIssue(
                    severity  = "warning",
                    code      = "MISSING_RETRY",
                    node_id   = nid,
                    message   = f"Node '{nid}' ({node_type}) makes external calls but has no retry policy.",
                    suggestion = "Add a retry block: {'max_attempts': 3, 'backoff_strategy': 'exponential', 'initial_delay': 'PT1S'}",
                    auto_fixable = True,
                ))

            # Long-running nodes should have timeout
            if node_type in ("action", "webhook", "ai", "human_approval", "loop") and not node.get("timeout"):
                issues.append(WorkflowIssue(
                    severity  = "info",
                    code      = "MISSING_TIMEOUT",
                    node_id   = nid,
                    message   = f"Node '{nid}' has no timeout configured.",
                    suggestion = "Add a timeout: {'duration': 'PT30S'} to prevent indefinite hanging.",
                    auto_fixable = True,
                ))

            # Human approval needs escalation
            if node_type == "human_approval":
                ha = node.get("human_approval", {})
                if not ha.get("approvers"):
                    issues.append(WorkflowIssue(
                        severity  = "error",
                        code      = "MISSING_APPROVERS",
                        node_id   = nid,
                        message   = f"Human approval node '{nid}' has no approvers defined.",
                        suggestion = "Add an 'approvers' list with at least one email address.",
                        auto_fixable = False,
                    ))

        return issues

    def _check_security(self, wf: Dict) -> List[WorkflowIssue]:
        issues = []
        import re
        # Check for hardcoded secrets
        wf_str = json.dumps(wf)
        secret_patterns = [
            (r"sk-[A-Za-z0-9\-_]{20,}", "OpenAI API key"),
            (r"xoxb-[A-Za-z0-9\-]+",    "Slack Bot Token"),
            (r"ghp_[A-Za-z0-9]{36}",    "GitHub Personal Access Token"),
            (r"AIza[A-Za-z0-9\-_]{35}", "Google API Key"),
            (r"Bearer [A-Za-z0-9\-._~+/]{20,}", "Bearer token"),
        ]
        for pattern, label in secret_patterns:
            if re.search(pattern, wf_str):
                issues.append(WorkflowIssue(
                    severity  = "error",
                    code      = "HARDCODED_SECRET",
                    node_id   = None,
                    message   = f"Possible hardcoded {label} detected in workflow JSON.",
                    suggestion = f"Move the {label} to a secret store and reference it via {{{{secrets.SECRET_NAME}}}}.",
                    auto_fixable = False,
                ))

        # Webhooks without auth
        for node in wf.get("nodes", []):
            if node.get("type") == "webhook":
                wh = node.get("webhook", {})
                if not wh.get("auth") and not wh.get("headers", {}).get("Authorization"):
                    issues.append(WorkflowIssue(
                        severity  = "warning",
                        code      = "UNAUTHENTICATED_WEBHOOK",
                        node_id   = node.get("id"),
                        message   = f"Webhook node '{node.get('id')}' has no authentication configured.",
                        suggestion = "Add an auth block or Authorization header to secure the webhook.",
                        auto_fixable = False,
                    ))

        return issues

    def _check_performance(self, wf: Dict) -> List[WorkflowIssue]:
        issues = []
        nodes = wf.get("nodes", [])

        # Check for sequential AI calls that could run in parallel
        ai_nodes = [n for n in nodes if n.get("type") == "ai"]
        if len(ai_nodes) >= 3:
            # Check if they form a linear chain
            ai_ids  = {n.get("id") for n in ai_nodes}
            ai_deps = [set(n.get("depends_on", [])) & ai_ids for n in ai_nodes]
            if any(deps for deps in ai_deps):
                issues.append(WorkflowIssue(
                    severity  = "info",
                    code      = "SEQUENTIAL_AI_CALLS",
                    node_id   = None,
                    message   = f"Found {len(ai_nodes)} AI nodes that may be running sequentially.",
                    suggestion = "Consider wrapping independent AI nodes in a 'parallel' block to reduce total runtime.",
                    auto_fixable = False,
                ))

        # Large parallel blocks
        for node in nodes:
            if node.get("type") == "parallel":
                branch_count = len(node.get("parallel", {}).get("branches", []))
                if branch_count > 10:
                    issues.append(WorkflowIssue(
                        severity  = "warning",
                        code      = "TOO_MANY_PARALLEL_BRANCHES",
                        node_id   = node.get("id"),
                        message   = f"Parallel node '{node.get('id')}' has {branch_count} branches (>10).",
                        suggestion = "Consider grouping branches or using a loop node with concurrency control.",
                    ))

        # Loop with no limit
        for node in nodes:
            if node.get("type") == "loop":
                lp = node.get("loop", {})
                if lp.get("mode") == "while" and not lp.get("max_iterations"):
                    issues.append(WorkflowIssue(
                        severity  = "warning",
                        code      = "UNBOUNDED_LOOP",
                        node_id   = node.get("id"),
                        message   = f"While loop node '{node.get('id')}' has no max_iterations limit.",
                        suggestion = "Add 'max_iterations: 100' to prevent infinite loops.",
                        auto_fixable = True,
                    ))

        return issues

    # ------------------------------------------------------------------
    # Layer 2: AI semantic analysis
    # ------------------------------------------------------------------

    def _ai_semantic_check(self, wf: Dict) -> List[WorkflowIssue]:
        """Use AI to detect logical and semantic issues."""
        compact = {
            "name":    wf.get("name"),
            "nodes": [{
                "id":         n.get("id"),
                "name":       n.get("name"),
                "type":       n.get("type"),
                "depends_on": n.get("depends_on", []),
                "description":n.get("description", ""),
            } for n in wf.get("nodes", [])]
        }
        messages = [
            {"role": "system", "content": """You are a workflow review expert. Analyze the workflow for logical/semantic issues.
Return JSON: {"issues": [{"severity": "error|warning|info", "code": "UPPERCASE_SNAKE", "node_id": "..." or null, "message": "...", "suggestion": "...", "auto_fixable": true|false}]}
Focus on: missing nodes, wrong ordering, logical gaps, missing error handlers, business logic issues.
Return at most 5 issues. If no issues, return {"issues": []}."""},
            {"role": "user", "content": f"Review this workflow for logical/semantic issues:\n{json.dumps(compact, indent=2)}"},
        ]
        try:
            result = self._ai.chat_json(messages, max_tokens=800)
            return [
                WorkflowIssue(
                    severity     = i.get("severity", "info"),
                    code         = i.get("code", "AI_ISSUE"),
                    node_id      = i.get("node_id"),
                    message      = i.get("message", ""),
                    suggestion   = i.get("suggestion", ""),
                    auto_fixable = i.get("auto_fixable", False),
                )
                for i in result.get("issues", [])
            ]
        except Exception:
            return []

    def _generate_summary(self, issues: List[WorkflowIssue]) -> str:
        errors   = [i for i in issues if i.severity == "error"]
        warnings = [i for i in issues if i.severity == "warning"]
        infos    = [i for i in issues if i.severity == "info"]
        if not issues:
            return "✅ No issues found. Workflow looks healthy!"
        parts = []
        if errors:   parts.append(f"❌ {len(errors)} error(s)")
        if warnings: parts.append(f"⚠️  {len(warnings)} warning(s)")
        if infos:    parts.append(f"ℹ️  {len(infos)} suggestion(s)")
        return " · ".join(parts)
