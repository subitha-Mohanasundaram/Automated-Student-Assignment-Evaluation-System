from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path

# Load environment variables from .env so worker and web server share config.
try:  # pragma: no cover
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

from assignment_intel.db import (
    claim_next_job,
    get_assignment,
    get_evaluation,
    get_submission,
    set_assignment_generation_status,
    update_job_finished,
)
from assignment_intel.problem_generation_pipeline import generate_problem_components
from assignment_intel.eval_service import run_evaluation
from assignment_intel.storage import StoredSubmission
from assignment_intel.daily_auto_assign import tick as daily_auto_assign_tick


def _now_utc() -> datetime:
    return datetime.utcnow()


def _ensure_logs() -> None:
    Path("logs").mkdir(parents=True, exist_ok=True)


def _append_jsonl(path: Path, obj: dict) -> None:
    _ensure_logs()
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=True) + "\n")


def process_job(job: dict) -> None:
    job_id = int(job["id"])
    job_type = str(job.get("type") or "")
    payload = job.get("payload") if isinstance(job.get("payload"), dict) else {}

    _append_jsonl(Path("logs") / "tool_calls.json", {"ts": _now_utc().isoformat() + "Z", "job_id": job_id, "job_type": job_type, "payload": payload})

    if job_type == "problem_generation":
        assignment_id = str(payload.get("assignment_id") or "")
        if not assignment_id:
            raise RuntimeError("missing_assignment_id")
        a = get_assignment(assignment_id=assignment_id)
        if not a:
            raise RuntimeError("assignment_not_found")
        set_assignment_generation_status(assignment_id=assignment_id, status="running", error=None, active=False)
        res = generate_problem_components(
            assignment_id=assignment_id,
            title=str(a.get("title") or ""),
            problem_description=str(a.get("description") or ""),
            max_retries=int(os.environ.get("AI_GEN_RETRIES", "3")),
        )
        if res.get("success") is not True:
            raise RuntimeError(str(res.get("error") or "generation_failed"))
        update_job_finished(job_id=job_id, status="completed", error=None, result=res)
        return

    if job_type == "solution_evaluation":
        evaluation_id = int(payload.get("evaluation_id") or 0)
        if not evaluation_id:
            raise RuntimeError("missing_evaluation_id")
        ev = get_evaluation(evaluation_id)
        if not ev:
            raise RuntimeError("evaluation_not_found")
        sub = get_submission(ev.submission_id)
        if not sub:
            raise RuntimeError("submission_not_found")
        stored = StoredSubmission(
            path=Path(str(sub["submission_path"])).resolve(),
            username=str(sub["username"]),
            problem_id=str(sub["problem_id"]),
            language=str(sub["language"]),
            saved_at=_now_utc(),
        )
        run_evaluation(evaluation_id, student_name=str(sub["student_name"]), stored=stored, problem_id=str(sub["problem_id"]))
        ev2 = get_evaluation(evaluation_id)
        _append_jsonl(
            Path("logs") / "evaluation_metrics.json",
            {
                "ts": _now_utc().isoformat() + "Z",
                "evaluation_id": evaluation_id,
                "problem_id": str(sub["problem_id"]),
                "username": str(sub["username"]),
                "language": str(sub["language"]),
                "status": str(ev2.status if ev2 else "unknown"),
                "score": float(ev2.score if ev2 else 0.0),
            },
        )
        update_job_finished(job_id=job_id, status="completed", error=None, result={"evaluation_id": evaluation_id})
        return

    raise RuntimeError(f"unknown_job_type: {job_type}")


def main() -> int:
    poll_s = float(os.environ.get("WORKER_POLL_S", "1.0"))
    print(f"[worker] starting (poll={poll_s}s)")
    while True:
        # Daily assignment auto-publisher (best-effort, never blocks worker).
        daily_auto_assign_tick()
        job = claim_next_job(types=["problem_generation", "solution_evaluation"])
        if not job:
            time.sleep(poll_s)
            continue
        job_id = int(job["id"])
        try:
            process_job(job)
        except Exception as exc:
            _append_jsonl(Path("logs") / "agent_trace.json", {"ts": _now_utc().isoformat() + "Z", "job_id": job_id, "error": str(exc)})
            try:
                update_job_finished(job_id=job_id, status="failed", error=str(exc), result=None)
            except Exception:
                pass
            # Best-effort: if this is a generation job, mark assignment failed.
            try:
                if str(job.get("type")) == "problem_generation":
                    aid = str((job.get("payload") or {}).get("assignment_id") or "")
                    if aid:
                        set_assignment_generation_status(assignment_id=aid, status="failed", error=str(exc), active=False)
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
