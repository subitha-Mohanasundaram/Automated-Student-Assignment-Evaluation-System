from __future__ import annotations

import json
from typing import Any

from agents.execution_agent import ExecutionAgent
from agents.problem_planner_agent import ProblemPlannerAgent
from evaluation.mcp_client import default_mcp_client

from assignment_intel.db import add_test_case, delete_all_test_cases, update_assignment_generation
from assignment_intel.db import set_assignment_generation_status


def _log_generation_error(record: dict[str, Any]) -> None:
    try:
        from pathlib import Path
        import json as _json

        Path("logs").mkdir(parents=True, exist_ok=True)
        p = Path("logs") / "ai_generation_errors.jsonl"
        with p.open("a", encoding="utf-8") as f:
            f.write(_json.dumps(record, ensure_ascii=True) + "\n")
    except Exception:
        pass


def _validate_generated_pack(
    *,
    meta: dict[str, Any],
    ref: dict[str, Any],
    tc: dict[str, Any],
    exp_vis: dict[str, Any],
    exp_hid: dict[str, Any],
    exp_str: dict[str, Any],
) -> None:
    code = str(ref.get("code") or "").strip()
    if not code:
        raise RuntimeError("validation_failed: empty_reference_solution")

    visible_inputs = tc.get("visible_inputs") if isinstance(tc.get("visible_inputs"), list) else []
    hidden_inputs = tc.get("hidden_inputs") if isinstance(tc.get("hidden_inputs"), list) else []
    stress_inputs = tc.get("stress_inputs") if isinstance(tc.get("stress_inputs"), list) else []
    if len(visible_inputs) < 3:
        raise RuntimeError("validation_failed: need_at_least_3_visible_tests")
    if len(hidden_inputs) < 1:
        raise RuntimeError("validation_failed: need_hidden_tests")
    if len(stress_inputs) < 1:
        raise RuntimeError("validation_failed: need_stress_tests")

    vis_out = exp_vis.get("outputs") if isinstance(exp_vis.get("outputs"), list) else []
    hid_out = exp_hid.get("outputs") if isinstance(exp_hid.get("outputs"), list) else []
    str_out = exp_str.get("outputs") if isinstance(exp_str.get("outputs"), list) else []
    if len(vis_out) != len(visible_inputs):
        raise RuntimeError("validation_failed: visible_outputs_mismatch")
    if len(hid_out) != len(hidden_inputs):
        raise RuntimeError("validation_failed: hidden_outputs_mismatch")
    if len(str_out) != len(stress_inputs):
        raise RuntimeError("validation_failed: stress_outputs_mismatch")

    # Sanity: non-empty inputs and deterministic outputs.
    def _norm(s: Any) -> str:
        return str(s or "").replace("\r\n", "\n").strip()

    def _check_inputs(name: str, xs: list[Any]) -> None:
        for i, x in enumerate(xs):
            if not _norm(x):
                raise RuntimeError(f"validation_failed: empty_{name}_input[{i}]")
            if len(_norm(x)) > 50_000:
                raise RuntimeError(f"validation_failed: {name}_input_too_large[{i}]")

    _check_inputs("visible", visible_inputs)
    _check_inputs("hidden", hidden_inputs)
    _check_inputs("stress", stress_inputs)

    # Prevent duplicate test inputs across packs (weakens grading).
    seen: set[str] = set()
    for pack_name, xs in [("visible", visible_inputs), ("hidden", hidden_inputs), ("stress", stress_inputs)]:
        for i, x in enumerate(xs):
            nx = _norm(x)
            if nx in seen:
                raise RuntimeError(f"validation_failed: duplicate_input_{pack_name}[{i}]")
            seen.add(nx)

    # Outputs should not be missing; allow blank only if the problem truly prints nothing (rare).
    if any(o is None for o in vis_out + hid_out + str_out):
        raise RuntimeError("validation_failed: missing_expected_outputs")

    # Sanity: examples present or at least constraints.
    examples = meta.get("examples")
    if not (isinstance(examples, list) and examples) and not str(meta.get("constraints") or "").strip():
        raise RuntimeError("validation_failed: missing_examples_and_constraints")


def _fallback_from_examples(meta: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Template generator: derive up to 3 visible IO tests from examples (no hidden disclosure)."""
    examples = meta.get("examples") if isinstance(meta.get("examples"), list) else []
    inputs: list[str] = []
    outputs: list[str] = []
    for ex in examples[:3]:
        if not isinstance(ex, dict):
            continue
        inp = str(ex.get("input") or "")
        out = str(ex.get("output") or "")
        if inp.strip() and out.strip():
            inputs.append(inp)
            outputs.append(out)
    while len(inputs) < 3:
        inputs.append("")
        outputs.append("")
    return inputs[:3], outputs[:3]


def generate_problem_components(
    *,
    assignment_id: str,
    title: str,
    problem_description: str,
    max_retries: int = 3,
) -> dict[str, Any]:
    """AI-driven problem generation using MCP tools (called through the local /mcp/call bridge).

    Requires AI_PROVIDER=openai and OPENAI_API_KEY for real generation.
    """
    set_assignment_generation_status(assignment_id=assignment_id, status="running", error=None, active=False)

    planner = ProblemPlannerAgent()
    executor = ExecutionAgent()
    client = default_mcp_client()

    last_tools: list[dict[str, Any]] = []
    last_meta: dict[str, Any] = {}

    for attempt in range(1, max(1, int(max_retries)) + 1):
        try:
            plan_msg = planner.plan(title=title, problem_description=problem_description)
            tool_calls = plan_msg.payload.get("tool_calls", [])
            if not isinstance(tool_calls, list):
                tool_calls = []

            exec_msg = executor.execute(mcp_client=client, tool_calls=tool_calls)
            results = exec_msg.payload.get("results", [])
            if not isinstance(results, list):
                results = []
            last_tools = results

            by_id: dict[str, Any] = {}
            for r in results:
                rid = str(r.get("id") or "")
                if rid:
                    by_id[rid] = r.get("result")

            def _require_success(key: str) -> dict[str, Any]:
                obj = by_id.get(key)
                if not isinstance(obj, dict) or obj.get("success") is not True:
                    raise RuntimeError(f"generation_step_failed: {key}: {obj}")
                det = obj.get("details")
                return det if isinstance(det, dict) else {}

            meta = _require_success("meta")
            last_meta = meta
            ref = _require_success("ref")
            tc = _require_success("tc")
            exp_vis = _require_success("exp_vis")
            exp_hid = _require_success("exp_hid")
            exp_str = _require_success("exp_str")

            _validate_generated_pack(meta=meta, ref=ref, tc=tc, exp_vis=exp_vis, exp_hid=exp_hid, exp_str=exp_str)

            visible_inputs = tc.get("visible_inputs") if isinstance(tc.get("visible_inputs"), list) else []
            hidden_inputs = tc.get("hidden_inputs") if isinstance(tc.get("hidden_inputs"), list) else []
            stress_inputs = tc.get("stress_inputs") if isinstance(tc.get("stress_inputs"), list) else []
            vis_out = exp_vis.get("outputs") if isinstance(exp_vis.get("outputs"), list) else []
            hid_out = exp_hid.get("outputs") if isinstance(exp_hid.get("outputs"), list) else []
            str_out = exp_str.get("outputs") if isinstance(exp_str.get("outputs"), list) else []

            update_assignment_generation(
                assignment_id=assignment_id,
                metadata=meta,
                constraints_text=str(meta.get("constraints") or ""),
                examples=meta.get("examples") if isinstance(meta.get("examples"), list) else [],
                difficulty=str(meta.get("difficulty") or ""),
                tags=meta.get("tags") if isinstance(meta.get("tags"), list) else [],
                reference_solution_lang=str(ref.get("language") or "python"),
                reference_solution_code=str(ref.get("code") or ""),
                generated_description=str(meta.get("generated_description") or ""),
                input_format=str(meta.get("input_format") or ""),
                output_format=str(meta.get("output_format") or ""),
            )

            # Replace test cases.
            delete_all_test_cases(assignment_id=assignment_id)
            for inp, out in zip(visible_inputs, vis_out):
                add_test_case(assignment_id=assignment_id, input_text=str(inp), expected_output=str(out), visibility="visible", weight=1.0)
            for inp, out in zip(hidden_inputs, hid_out):
                add_test_case(assignment_id=assignment_id, input_text=str(inp), expected_output=str(out), visibility="hidden", weight=1.0)
            for inp, out in zip(stress_inputs, str_out):
                add_test_case(assignment_id=assignment_id, input_text=str(inp), expected_output=str(out), visibility="stress", weight=1.0)

            set_assignment_generation_status(assignment_id=assignment_id, status="completed", error=None, active=True)
            return {
                "success": True,
                "details": {
                    "assignment_id": assignment_id,
                    "meta": meta,
                    "reference_solution_lang": str(ref.get("language") or "python"),
                    "visible_tests": len(visible_inputs),
                    "hidden_tests": len(hidden_inputs),
                    "stress_tests": len(stress_inputs),
                },
                "tool_results": results,
            }
        except Exception as exc:
            rec = {
                "assignment_id": assignment_id,
                "attempt": attempt,
                "title": title,
                "error": str(exc),
            }
            _log_generation_error(rec)
            if attempt >= max(1, int(max_retries)):
                break

    # Fallback: keep assignment inactive but publish at least 3 visible tests from examples (if any).
    vis_inp, vis_out = _fallback_from_examples(last_meta or {})
    try:
        delete_all_test_cases(assignment_id=assignment_id)
        for inp, out in zip(vis_inp, vis_out):
            add_test_case(assignment_id=assignment_id, input_text=str(inp), expected_output=str(out), visibility="visible", weight=1.0)
    except Exception:
        pass

    set_assignment_generation_status(
        assignment_id=assignment_id,
        status="failed",
        error="ai_generation_failed_after_retries",
        active=False,
    )
    return {"success": False, "error": "ai_generation_failed_after_retries", "tool_results": last_tools}
