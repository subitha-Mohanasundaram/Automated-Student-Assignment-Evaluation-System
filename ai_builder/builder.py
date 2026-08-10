"""
WorkflowBuilder — Main Orchestrator
====================================
The central class that ties all Phase 7 components together.

Usage:
    from ai_builder import WorkflowBuilder

    builder = WorkflowBuilder()

    # Generate from natural language
    result = builder.build("When a GitHub PR is merged, post to Slack and open a Jira ticket")
    print(result.explanation)

    # Explain an existing workflow
    explain = builder.explain(result.workflow_json)
    print(explain.summary)

    # Detect mistakes
    issues = builder.diagnose(result.workflow_json)
    for issue in issues.issues:
        print(f"[{issue.severity}] {issue.message}")

    # Estimate cost and runtime
    estimate = builder.estimate(result.workflow_json)
    print(estimate.summary_text())

    # Get improvement suggestions
    suggestions = builder.suggest(result.workflow_json)
    for s in suggestions.suggestions:
        print(f"[{s.priority}] {s.title}")

    # Edit with natural language
    edit = builder.edit(result.workflow_json, "Add retry to all action nodes")
    print(edit.diff_summary)

    # Generate architecture diagram
    arch = builder.architecture(result.workflow_json)
    print(arch.mermaid)

    # Interactive chat
    builder.chat()
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv

from ai_builder.ai_client import AIClient
from ai_builder.architect import ArchitectureGenerator
from ai_builder.detector import MistakeDetector
from ai_builder.editor import NLEditor
from ai_builder.estimator import CostEstimator
from ai_builder.explainer import WorkflowExplainer
from ai_builder.generator import WorkflowGenerator
from ai_builder.models import (
    ArchitectureResult, BuildResult, DiagnoseResult,
    EditResult, EstimateResult, ExplainResult, SuggestionResult,
)
from ai_builder.suggester import ImprovementSuggester

# Load .env from project root
load_dotenv(Path(__file__).parent.parent / ".env")


class WorkflowBuilder:
    """
    AI Workflow Builder — the main entry point for Phase 7.

    All methods are pure functions: they take inputs and return typed result
    objects without storing mutable state between calls, making the builder
    safe to use concurrently.
    """

    def __init__(
        self,
        model:        str   = "gpt-4o-mini",
        temperature:  float = 0.2,
        runs_per_day: int   = 100,
        verbose:      bool  = False,
    ) -> None:
        # Use env override if set
        model = os.environ.get("OPENAI_MODEL", model)

        self._client    = AIClient(model=model, temperature=temperature)
        self._generator = WorkflowGenerator(self._client)
        self._explainer = WorkflowExplainer(self._client)
        self._detector  = MistakeDetector(self._client)
        self._estimator = CostEstimator(runs_per_day=runs_per_day)
        self._suggester = ImprovementSuggester(self._client, self._estimator)
        self._editor    = NLEditor(self._client)
        self._architect = ArchitectureGenerator(self._client)
        self._verbose   = verbose
        self._runs_per_day = runs_per_day

    # ------------------------------------------------------------------
    # Primary API
    # ------------------------------------------------------------------

    def build(
        self,
        intent:  str,
        context: Optional[Dict[str, Any]] = None,
    ) -> BuildResult:
        """
        Generate a complete workflow from a natural language description.

        Args:
            intent:  Plain English description of what the workflow should do.
            context: Optional dict with extra context (org name, timezone, etc.)

        Returns:
            BuildResult with workflow_json, explanation, and metadata.
        """
        if self._verbose:
            print(f"🔨 Generating workflow for: {intent[:80]}...")
        return self._generator.generate(intent, context)

    def explain(self, workflow_json: Dict[str, Any]) -> ExplainResult:
        """
        Explain a workflow in plain English.

        Returns a step-by-step explanation, data flow description,
        and per-node plain-language descriptions.
        """
        if self._verbose:
            print(f"📖 Explaining workflow: {workflow_json.get('name', 'unknown')}...")
        return self._explainer.explain(workflow_json)

    def diagnose(self, workflow_json: Dict[str, Any]) -> DiagnoseResult:
        """
        Detect mistakes, structural issues, and best-practice violations.

        Runs both deterministic rule checks (DAG validation, security
        patterns, reliability gaps) and AI semantic analysis.
        """
        if self._verbose:
            print(f"🔍 Diagnosing workflow: {workflow_json.get('name', 'unknown')}...")
        return self._detector.detect(workflow_json)

    def estimate(
        self,
        workflow_json: Dict[str, Any],
        runs_per_day: Optional[int] = None,
    ) -> EstimateResult:
        """
        Estimate cost (USD) and runtime (milliseconds) for a workflow.

        Uses pricing tables for OpenAI, Google APIs, email services, etc.
        Returns per-node breakdown plus daily and monthly totals.
        """
        if self._verbose:
            print(f"💰 Estimating cost/runtime for: {workflow_json.get('name', 'unknown')}...")
        return self._estimator.estimate(workflow_json, runs_per_day or self._runs_per_day)

    def suggest(self, workflow_json: Dict[str, Any]) -> SuggestionResult:
        """
        Generate improvement suggestions and optimization proposals.

        Combines AI-powered analysis with deterministic pattern detection
        for performance, reliability, cost, security, and UX improvements.
        """
        if self._verbose:
            print(f"💡 Generating suggestions for: {workflow_json.get('name', 'unknown')}...")
        return self._suggester.suggest(workflow_json)

    def edit(
        self,
        workflow_json: Dict[str, Any],
        command:       str,
    ) -> EditResult:
        """
        Apply a natural language edit command to the workflow.

        Examples:
          "Move Email before Slack"
          "Replace Gmail with Outlook"
          "Add retry to fetch_data node"
          "Add a 30-second delay after send_notification"
          "Wrap ai_analysis and ai_summary in parallel"
          "Set timeout on process_data to 60 seconds"
          "Rename extract_data to parse_response"
          "Remove the human_approval node"
          "Add error handler to all action nodes"
        """
        if self._verbose:
            print(f"✏️  Editing workflow: '{command}'")
        return self._editor.edit(workflow_json, command)

    def architecture(self, workflow_json: Dict[str, Any]) -> ArchitectureResult:
        """
        Generate architecture diagrams and descriptions.

        Returns:
          - mermaid:    Mermaid LR flowchart (paste into GitHub/Notion)
          - ascii_art:  Terminal-friendly box diagram
          - description: Prose architecture description
          - components: List of component dicts
          - data_flows: List of edge dicts
        """
        if self._verbose:
            print(f"🏗️  Generating architecture for: {workflow_json.get('name', 'unknown')}...")
        return self._architect.generate(workflow_json)

    # ------------------------------------------------------------------
    # Compound operations
    # ------------------------------------------------------------------

    def build_and_review(self, intent: str) -> Dict[str, Any]:
        """
        Build a workflow and immediately run all analysis steps.
        Returns a dict with build, diagnose, estimate, suggest, arch.
        """
        build = self.build(intent)
        if not build.success:
            return {"build": build, "error": build.error}

        wf = build.workflow_json
        return {
            "build":        build,
            "explain":      self.explain(wf),
            "diagnose":     self.diagnose(wf),
            "estimate":     self.estimate(wf),
            "suggest":      self.suggest(wf),
            "architecture": self.architecture(wf),
        }

    def apply_suggestions(
        self,
        workflow_json: Dict[str, Any],
        auto_only: bool = True,
    ) -> EditResult:
        """
        Auto-apply all auto_applicable suggestions at once.
        Returns the final edited workflow after all changes.
        """
        suggestions = self.suggest(workflow_json)
        applicable  = [
            s for s in suggestions.suggestions
            if (s.auto_applicable or not auto_only) and s.action
        ]

        if not applicable:
            return EditResult(
                success         = True,
                original_workflow = workflow_json,
                updated_workflow  = workflow_json,
                changes         = [],
                diff_summary    = "No auto-applicable suggestions found.",
            )

        current = workflow_json
        all_changes = []
        for sug in applicable:
            result = self.edit(current, sug.action)
            if result.success and result.updated_workflow:
                current     = result.updated_workflow
                all_changes.extend(result.changes)

        return EditResult(
            success           = True,
            original_workflow = workflow_json,
            updated_workflow  = current,
            changes           = all_changes,
            diff_summary      = f"Applied {len(applicable)} suggestion(s):\n" + "\n".join(f"  • {c}" for c in all_changes),
        )

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def save(self, workflow_json: Dict[str, Any], path: str) -> None:
        """Save workflow JSON to a file."""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(workflow_json, f, indent=2)
        if self._verbose:
            print(f"💾 Saved to {path}")

    def load(self, path: str) -> Dict[str, Any]:
        """Load a workflow JSON from a file."""
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    # ------------------------------------------------------------------
    # Session stats
    # ------------------------------------------------------------------

    @property
    def session_cost_usd(self) -> float:
        """Total AI API cost incurred this session."""
        return self._client.session_cost_usd

    @property
    def session_tokens(self) -> Dict[str, int]:
        """Total tokens used this session."""
        return self._client.session_tokens
