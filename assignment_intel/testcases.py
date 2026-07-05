from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from assignment_intel.db import list_test_cases


@dataclass(frozen=True)
class IOTestCase:
    input_text: str
    expected_output: str
    visibility: str  # visible|hidden
    weight: float = 1.0


def load_io_test_cases(assignment_id: str) -> list[IOTestCase]:
    """Loads IO testcases from SQLite for the given assignment_id.

    Returns an empty list if none exist (caller should fall back to legacy evaluation mode).
    """
    rows = list_test_cases(assignment_id=assignment_id)
    out: list[IOTestCase] = []
    for r in rows:
        out.append(
            IOTestCase(
                input_text=str(r.get("input_text") or ""),
                expected_output=str(r.get("expected_output") or ""),
                visibility=str(r.get("visibility") or "visible"),
                weight=float(r.get("weight") or 1.0),
            )
        )
    return out


def summarize_cases(cases: list[IOTestCase]) -> dict[str, Any]:
    visible = [c for c in cases if c.visibility == "visible"]
    hidden = [c for c in cases if c.visibility != "visible"]
    return {
        "total": len(cases),
        "visible": len(visible),
        "hidden": len(hidden),
        "total_weight": round(sum(float(c.weight) for c in cases), 4),
    }

