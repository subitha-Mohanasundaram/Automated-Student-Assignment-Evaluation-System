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
