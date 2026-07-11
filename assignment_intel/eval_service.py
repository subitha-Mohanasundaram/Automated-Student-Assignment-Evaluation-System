from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from assignment_intel.db import (
    DB_PATH,
    create_evaluation,
    create_submission,
    get_evaluation,
    update_evaluation_finished,
    update_evaluation_running,
)
from assignment_intel.models import Submission
from assignment_intel.orchestrator import build_default_registry, run_pipeline, save_report
from assignment_intel.storage import StoredSubmission, safe_slug


def _utc_ts() -> str:
    return datetime.utcnow().strftime("%Y%m%d_%H%M%S")


def enqueue_and_run(
    *,
    stored: StoredSubmission,
    student_name: str,
    phone: str | None = None,
    problem_id: str,
    db_path: Path = DB_PATH,
) -> int:
    submission_row = create_submission(
        student_name=student_name,
        username=stored.username,
        phone=phone,
        problem_id=stored.problem_id,
        language=stored.language,
        submission_path=stored.path,
        db_path=db_path,
    )
    evaluation_row = create_evaluation(submission_id=submission_row.id, db_path=db_path)
    run_evaluation(evaluation_row.id, student_name=student_name, stored=stored, problem_id=problem_id, db_path=db_path)
    return evaluation_row.id


def enqueue_only(
    *,
    stored: StoredSubmission,
    student_name: str,
    phone: str | None = None,
    db_path: Path = DB_PATH,
) -> int:
    """Create submission+evaluation rows but do not run evaluation (for background workers)."""
    submission_row = create_submission(
        student_name=student_name,
        username=stored.username,
        phone=phone,
        problem_id=stored.problem_id,
        language=stored.language,
        submission_path=stored.path,
        db_path=db_path,
    )
    evaluation_row = create_evaluation(submission_id=submission_row.id, db_path=db_path)
    return evaluation_row.id


def run_evaluation(
    evaluation_id: int,
    *,
    student_name: str,
    stored: StoredSubmission,
    problem_id: str,
    db_path: Path = DB_PATH,
) -> None:
    update_evaluation_running(evaluation_id=evaluation_id, db_path=db_path)

    submission = Submission(
        student_name=student_name,
        submission_path=stored.path,
        problem_id=stored.problem_id,
        language=stored.language,
    )

    try:
        registry = build_default_registry()
        report = run_pipeline(registry, submission)
        ts = _utc_ts()
        report_dir = Path("results") / "reports"
        report_path = report_dir / f"{stored.username}_{stored.problem_id}_{ts}.json"
        save_report(report, report_path)

        results = report.results.get("analysis", {}).get("results", {})
        relevance = report.results.get("analysis", {}).get("relevance", {})
        score = float(results.get("score", 0.0) or 0.0)
        result_json_path = None
        if isinstance(results, dict) and results.get("result_json"):
            result_json_path = Path(str(results["result_json"]))

        # If relevance check failed or grading tool failed, mark evaluation as failed (clear UX vs silent 0 score).
        status = "completed"
        error_msg = None
        # Relevance
        if isinstance(relevance, dict) and relevance.get("relevant") is False:
            status = "failed"
            score = 0.0
            error_msg = str(relevance.get("reason") or "irrelevant_solution")
        # Tool failure
        for tr in report.tool_results:
            if tr.tool == "evaluate_submission" and not tr.ok:
                status = "failed"
                score = 0.0
                error_msg = tr.error or "evaluation_failed"
                break

        update_evaluation_finished(
            evaluation_id=evaluation_id,
            status=status,
            score=score,
            report_path=report_path,
            result_json_path=result_json_path,
            tool_results=[asdict(t) for t in report.tool_results],
            error=error_msg,
            db_path=db_path,
        )

        # ── CodeMentor ReAct Agent ──────────────────────────────────────
        # Run AFTER score is saved so the student gets AI feedback in their
        # report. Failures here are non-fatal — evaluation already completed.
        if status == "completed":
            _run_codementor_agent(
                report_path=report_path,
                stored=stored,
                results=results,
            )
    except Exception as exc:
        update_evaluation_finished(
            evaluation_id=evaluation_id,
            status="failed",
            score=0.0,
            report_path=None,
            result_json_path=None,
            tool_results=[],
            error=str(exc),
            db_path=db_path,
        )


def _run_codementor_agent(
    *,
    report_path: Path,
    stored: StoredSubmission,
    results: dict,
) -> None:
    """Run the CodeMentor ReAct Agent and inject ai_feedback into the report JSON.

    Called automatically after every completed evaluation.
    Failures are silently caught — the evaluation score is already saved.
    """
    import os

    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        return  # Agent disabled — no key configured

    if not report_path or not report_path.exists():
        return

    try:
        # Build the result dict the agent expects
        result_payload: dict = {
            "problem_id": stored.problem_id,
            "language": stored.language,
            "score": float(results.get("score", 0.0) or 0.0),
            "passed_cases": int(results.get("passed_cases", 0) or 0),
            "total_test_cases": int(results.get("total_test_cases", 0) or 0),
            "case_results": results.get("case_results") or [],
        }

        student_code = ""
        try:
            student_code = Path(stored.path).read_text(encoding="utf-8", errors="replace")
        except Exception:
            return  # No code to analyze

        # Build ChromaDB store (fast, idempotent)
        try:
            from rag.problem_store import build_store
            build_store()
        except Exception:
            pass  # Falls back to direct JSON read

        from agents.codementor_agent import explain_failures
        output = explain_failures(
            problem_id=stored.problem_id,
            student_code=student_code,
            result=result_payload,
            api_key=api_key,
        )

        ai_feedback = {
            "explanation": output.explanation,
            "likely_cause": output.likely_cause,
            "root_cause": output.root_cause,
            "why_hidden_fail": output.why_hidden_fail,
            "hint": output.hint,
            "confidence": output.confidence,
            "tools_used": output.tools_used,
            "reasoning_turns": output.reasoning_turns,
        }

        # Inject into the saved report JSON
        report_data = json.loads(report_path.read_text(encoding="utf-8"))
        if "analysis" not in report_data:
            report_data["analysis"] = {}
        report_data["analysis"]["ai_feedback"] = ai_feedback
        report_path.write_text(json.dumps(report_data, indent=2), encoding="utf-8")

        print(
            f"[codementor] ai_feedback injected into {report_path.name} "
            f"(confidence={output.confidence}, turns={output.reasoning_turns})",
            flush=True,
        )

    except Exception as exc:
        # Never crash the evaluation pipeline
        print(f"[codementor] agent skipped: {exc}", flush=True)
