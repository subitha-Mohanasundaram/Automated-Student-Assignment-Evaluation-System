"""
Phase 7 — AI Workflow Builder
==============================
An intelligent assistant that understands natural language, generates
workflow JSON, explains, detects mistakes, suggests improvements,
estimates cost/runtime, and accepts natural-language edits.

Quick start:
    from ai_builder import WorkflowBuilder
    builder = WorkflowBuilder()
    result  = builder.build("When a GitHub PR is merged, post to Slack and create a Jira ticket")
    print(result.workflow_json)
    print(result.explanation)
"""

from ai_builder.builder import WorkflowBuilder
from ai_builder.models import (
    BuildResult, ExplainResult, DiagnoseResult,
    EstimateResult, EditResult, SuggestionResult,
)

__all__ = [
    "WorkflowBuilder",
    "BuildResult", "ExplainResult", "DiagnoseResult",
    "EstimateResult", "EditResult", "SuggestionResult",
]
__version__ = "1.0.0"
