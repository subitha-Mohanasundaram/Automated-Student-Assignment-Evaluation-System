"""
AI Builder Data Models
======================
All result types returned by the WorkflowBuilder methods.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Build result
# ---------------------------------------------------------------------------

@dataclass
class BuildResult:
    """Result of building a workflow from natural language intent."""
    success:         bool
    workflow_json:   Optional[Dict[str, Any]]   = None
    workflow_id:     Optional[str]              = None
    name:            Optional[str]              = None
    explanation:     str                        = ""
    node_count:      int                        = 0
    trigger_type:    Optional[str]              = None
    plugins_used:    List[str]                  = field(default_factory=list)
    error:           Optional[str]              = None
    raw_intent:      Optional[str]              = None
    confidence:      float                      = 0.0
    generated_at:    datetime                   = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success":       self.success,
            "workflow_id":   self.workflow_id,
            "name":          self.name,
            "explanation":   self.explanation,
            "node_count":    self.node_count,
            "plugins_used":  self.plugins_used,
            "confidence":    self.confidence,
            "error":         self.error,
        }


# ---------------------------------------------------------------------------
# Explain result
# ---------------------------------------------------------------------------

@dataclass
class NodeExplanation:
    node_id:     str
    node_type:   str
    plain:       str         # one-sentence plain English
    purpose:     str         # why this node exists
    inputs:      List[str]   = field(default_factory=list)
    outputs:     List[str]   = field(default_factory=list)


@dataclass
class ExplainResult:
    """Plain-English explanation of a workflow."""
    success:       bool
    summary:       str                        = ""
    steps:         List[str]                  = field(default_factory=list)
    node_details:  List[NodeExplanation]      = field(default_factory=list)
    data_flow:     str                        = ""
    prerequisites: List[str]                  = field(default_factory=list)
    error:         Optional[str]              = None


# ---------------------------------------------------------------------------
# Diagnose result
# ---------------------------------------------------------------------------

@dataclass
class WorkflowIssue:
    severity:    str          # "error" | "warning" | "info"
    code:        str          # e.g. "MISSING_RETRY"
    node_id:     Optional[str]
    message:     str
    suggestion:  str
    auto_fixable:bool         = False


@dataclass
class DiagnoseResult:
    """Detected mistakes and issues in a workflow."""
    success:      bool
    issues:       List[WorkflowIssue]   = field(default_factory=list)
    error_count:  int                   = 0
    warning_count:int                   = 0
    info_count:   int                   = 0
    health_score: float                 = 100.0   # 0–100
    summary:      str                   = ""
    error:        Optional[str]         = None

    def __post_init__(self) -> None:
        self.error_count   = sum(1 for i in self.issues if i.severity == "error")
        self.warning_count = sum(1 for i in self.issues if i.severity == "warning")
        self.info_count    = sum(1 for i in self.issues if i.severity == "info")
        total = len(self.issues)
        if total:
            deductions = self.error_count * 20 + self.warning_count * 5 + self.info_count * 1
            self.health_score = max(0.0, 100.0 - deductions)


# ---------------------------------------------------------------------------
# Estimate result
# ---------------------------------------------------------------------------

@dataclass
class NodeCostEstimate:
    node_id:          str
    node_type:        str
    cost_usd_per_run: float
    runtime_ms:       int
    notes:            str = ""


@dataclass
class EstimateResult:
    """Cost and runtime estimates for a workflow."""
    success:              bool
    node_estimates:       List[NodeCostEstimate]   = field(default_factory=list)
    # Cost
    cost_per_run_usd:     float                    = 0.0
    cost_per_day_usd:     float                    = 0.0
    cost_per_month_usd:   float                    = 0.0
    # Runtime
    estimated_runtime_ms: int                      = 0
    critical_path_ms:     int                      = 0
    # Breakdown
    ai_cost_usd:          float                    = 0.0
    api_cost_usd:         float                    = 0.0
    compute_cost_usd:     float                    = 0.0
    # Assumptions
    runs_per_day:         int                      = 100
    assumptions:          List[str]                = field(default_factory=list)
    error:                Optional[str]            = None

    def summary_text(self) -> str:
        lines = [
            f"Cost per run  : ${self.cost_per_run_usd:.4f}",
            f"Cost per day  : ${self.cost_per_day_usd:.2f}  ({self.runs_per_day} runs/day)",
            f"Cost per month: ${self.cost_per_month_usd:.2f}",
            f"Runtime       : {self.estimated_runtime_ms}ms  (critical path: {self.critical_path_ms}ms)",
            f"  ├─ AI costs   : ${self.ai_cost_usd:.4f}",
            f"  ├─ API costs  : ${self.api_cost_usd:.4f}",
            f"  └─ Compute    : ${self.compute_cost_usd:.4f}",
        ]
        if self.assumptions:
            lines.append("\nAssumptions:")
            for a in self.assumptions:
                lines.append(f"  • {a}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Edit result
# ---------------------------------------------------------------------------

@dataclass
class EditResult:
    """Result of applying a natural-language edit to a workflow."""
    success:          bool
    original_workflow: Optional[Dict[str, Any]] = None
    updated_workflow:  Optional[Dict[str, Any]] = None
    command_parsed:    Optional[str]            = None
    changes:           List[str]                = field(default_factory=list)
    diff_summary:      str                      = ""
    error:             Optional[str]            = None


# ---------------------------------------------------------------------------
# Suggestion result
# ---------------------------------------------------------------------------

@dataclass
class Suggestion:
    category:    str          # "performance" | "reliability" | "cost" | "security" | "ux"
    priority:    str          # "high" | "medium" | "low"
    title:       str
    description: str
    action:      str          # NL command to apply the suggestion
    estimated_impact: str     = ""
    auto_applicable:  bool    = False


@dataclass
class OptimizationResult:
    """Optimization suggestions for a workflow."""
    suggestion:      Suggestion
    before_estimate: Optional[EstimateResult] = None
    after_estimate:  Optional[EstimateResult] = None
    savings_pct:     float                    = 0.0


@dataclass
class SuggestionResult:
    """AI-generated improvement suggestions."""
    success:       bool
    suggestions:   List[Suggestion]         = field(default_factory=list)
    optimizations: List[OptimizationResult] = field(default_factory=list)
    summary:       str                      = ""
    error:         Optional[str]            = None


# ---------------------------------------------------------------------------
# Architecture result
# ---------------------------------------------------------------------------

@dataclass
class ArchitectureResult:
    """Generated architecture representation."""
    success:      bool
    mermaid:      str           = ""   # Mermaid flowchart diagram
    ascii_art:    str           = ""   # ASCII text diagram
    description:  str           = ""   # Prose description
    components:   List[Dict]    = field(default_factory=list)
    data_flows:   List[Dict]    = field(default_factory=list)
    error:        Optional[str] = None
