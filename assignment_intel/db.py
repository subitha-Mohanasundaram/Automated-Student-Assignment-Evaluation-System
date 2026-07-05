from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


DB_PATH = Path("results") / "platform.db"


def _utcnow_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def get_conn(db_path: Path = DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path = DB_PATH) -> None:
    with get_conn(db_path) as conn:
        conn.executescript(
            """
            PRAGMA journal_mode=WAL;
            PRAGMA foreign_keys=ON;

            CREATE TABLE IF NOT EXISTS users (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              username TEXT NOT NULL UNIQUE,
              email TEXT NOT NULL UNIQUE,
              password_hash TEXT NOT NULL,
              phone TEXT,
              role TEXT NOT NULL DEFAULT 'student', -- student|instructor|admin
              created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_users_role
              ON users(role, id);

            CREATE TABLE IF NOT EXISTS assignments (
              id TEXT PRIMARY KEY,
              title TEXT NOT NULL,
              description TEXT NOT NULL DEFAULT '',
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS test_cases (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              assignment_id TEXT NOT NULL,
              input_text TEXT NOT NULL,
              expected_output TEXT NOT NULL,
              visibility TEXT NOT NULL DEFAULT 'visible', -- visible|hidden
              weight REAL NOT NULL DEFAULT 1.0,
              created_at TEXT NOT NULL,
              FOREIGN KEY(assignment_id) REFERENCES assignments(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_test_cases_assignment
              ON test_cases(assignment_id, visibility, id);

            CREATE TABLE IF NOT EXISTS jobs (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              type TEXT NOT NULL, -- problem_generation|solution_evaluation
              payload_json TEXT NOT NULL DEFAULT '{}',
              status TEXT NOT NULL DEFAULT 'queued', -- queued|running|completed|failed
              error TEXT,
              result_json TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_jobs_status
              ON jobs(status, id);

            CREATE TABLE IF NOT EXISTS submissions (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              student_name TEXT NOT NULL,
              username TEXT NOT NULL,
              phone TEXT,
              problem_id TEXT NOT NULL,
              language TEXT NOT NULL,
              submission_path TEXT NOT NULL,
              created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_submissions_user_problem
              ON submissions(username, problem_id, created_at);

            CREATE TABLE IF NOT EXISTS evaluations (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              submission_id INTEGER NOT NULL,
              status TEXT NOT NULL,
              score REAL NOT NULL DEFAULT 0,
              report_path TEXT,
              result_json_path TEXT,
              error TEXT,
              tool_results_json TEXT NOT NULL DEFAULT '[]',
              created_at TEXT NOT NULL,
              finished_at TEXT,
              FOREIGN KEY(submission_id) REFERENCES submissions(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_evals_submission
              ON evaluations(submission_id, created_at);
            """
        )

        # Lightweight migrations for new columns (SQLite supports ADD COLUMN).
        def _has_col(table: str, col: str) -> bool:
            rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
            return any(r["name"] == col for r in rows)

        def _add_col(table: str, col: str, col_type: str) -> None:
            if not _has_col(table, col):
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")

        _add_col("assignments", "metadata_json", "TEXT")
        _add_col("assignments", "constraints_text", "TEXT")
        _add_col("assignments", "examples_json", "TEXT")
        _add_col("assignments", "difficulty", "TEXT")
        _add_col("assignments", "tags_json", "TEXT")
        _add_col("assignments", "reference_solution_lang", "TEXT")
        _add_col("assignments", "reference_solution_code", "TEXT")
        _add_col("assignments", "generated_description", "TEXT")
        _add_col("assignments", "input_format", "TEXT")
        _add_col("assignments", "output_format", "TEXT")
        _add_col("assignments", "examples_text", "TEXT")
        _add_col("assignments", "generation_status", "TEXT")  # queued|running|completed|failed
        _add_col("assignments", "generation_error", "TEXT")
        _add_col("assignments", "active", "INTEGER")  # 1=visible to students
        _add_col("assignments", "archived", "INTEGER")  # 1=hidden from students/instructors unless explicitly shown
        _add_col("submissions", "phone", "TEXT")

        # Backfill: older assignments with visible tests should be active by default.
        try:
            conn.execute(
                """
                UPDATE assignments
                   SET active=1
                 WHERE active IS NULL
                   AND (SELECT COUNT(1) FROM test_cases t WHERE t.assignment_id=assignments.id AND t.visibility='visible') > 0
                """
            )
        except Exception:
            pass

        # Backfill archived default.
        try:
            conn.execute("UPDATE assignments SET archived=0 WHERE archived IS NULL")
        except Exception:
            pass


def upsert_assignment(*, assignment_id: str, title: str, description: str = "", db_path: Path = DB_PATH) -> None:
    init_db(db_path)
    created_at = _utcnow_iso()
    with get_conn(db_path) as conn:
        conn.execute(
            """
            INSERT INTO assignments(id, title, description, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET title=excluded.title, description=excluded.description
            """,
            (assignment_id, title, description, created_at),
        )


def update_assignment_generation(
    *,
    assignment_id: str,
    metadata: dict[str, Any] | None = None,
    constraints_text: str | None = None,
    examples: list[dict[str, Any]] | None = None,
    difficulty: str | None = None,
    tags: list[str] | None = None,
    reference_solution_lang: str | None = None,
    reference_solution_code: str | None = None,
    generated_description: str | None = None,
    input_format: str | None = None,
    output_format: str | None = None,
    examples_text: str | None = None,
    db_path: Path = DB_PATH,
) -> None:
    init_db(db_path)
    with get_conn(db_path) as conn:
        conn.execute(
            """
            UPDATE assignments
               SET metadata_json=?,
                   constraints_text=?,
                   examples_json=?,
                   difficulty=?,
                   tags_json=?,
                   generated_description=?,
                   input_format=?,
                   output_format=?,
                   examples_text=?,
                   reference_solution_lang=?,
                   reference_solution_code=?
             WHERE id=?
            """,
            (
                json.dumps(metadata or {}) if metadata is not None else None,
                constraints_text,
                json.dumps(examples or []) if examples is not None else None,
                difficulty,
                json.dumps(tags or []) if tags is not None else None,
                generated_description,
                input_format,
                output_format,
                examples_text,
                reference_solution_lang,
                reference_solution_code,
                assignment_id,
            ),
        )


def set_assignment_generation_status(
    *,
    assignment_id: str,
    status: str,
    error: str | None = None,
    active: bool | None = None,
    db_path: Path = DB_PATH,
) -> None:
    init_db(db_path)
    st = (status or "").strip().lower()
    if st not in {"queued", "running", "completed", "failed"}:
        st = "queued"
    with get_conn(db_path) as conn:
        conn.execute(
            """
            UPDATE assignments
               SET generation_status=?,
                   generation_error=?,
                   active=COALESCE(?, active)
             WHERE id=?
            """,
            (st, error, (1 if active else 0) if active is not None else None, assignment_id),
        )


def add_test_case(
    *,
    assignment_id: str,
    input_text: str,
    expected_output: str,
    visibility: str = "visible",
    weight: float = 1.0,
    db_path: Path = DB_PATH,
) -> None:
    init_db(db_path)
    created_at = _utcnow_iso()
    vis = visibility.strip().lower()
    if vis not in {"visible", "hidden", "stress"}:
        vis = "visible"
    with get_conn(db_path) as conn:
        conn.execute(
            """
            INSERT INTO test_cases(assignment_id, input_text, expected_output, visibility, weight, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (assignment_id, input_text, expected_output, vis, float(weight), created_at),
        )


def list_test_cases(*, assignment_id: str, db_path: Path = DB_PATH) -> list[dict[str, Any]]:
    init_db(db_path)
    with get_conn(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, assignment_id, input_text, expected_output, visibility, weight
              FROM test_cases
             WHERE assignment_id=?
          ORDER BY id ASC
            """,
            (assignment_id,),
        ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        out.append({k: r[k] for k in r.keys()})
    return out


def list_recent_evaluations_for_problem(problem_id: str, limit: int = 200, db_path: Path = DB_PATH) -> list[dict[str, Any]]:
    init_db(db_path)
    with get_conn(db_path) as conn:
        rows = conn.execute(
            """
            SELECT e.id as evaluation_id,
                   e.status,
                   e.score,
                   e.report_path,
                   e.result_json_path,
                   e.error,
                   e.created_at,
                   e.finished_at,
                   s.id AS submission_id,
                   s.student_name,
                   s.username,
                   s.phone,
                   s.problem_id,
                   s.language,
                   s.submission_path
              FROM evaluations e
              JOIN submissions s ON s.id = e.submission_id
             WHERE s.problem_id = ?
          ORDER BY e.id DESC
             LIMIT ?
            """,
            (problem_id, int(limit)),
        ).fetchall()
    return [{k: r[k] for k in r.keys()} for r in rows]


def get_latest_submission_for_user_problem(*, username: str, problem_id: str, db_path: Path = DB_PATH) -> dict[str, Any] | None:
    init_db(db_path)
    with get_conn(db_path) as conn:
        row = conn.execute(
            """
            SELECT *
              FROM submissions
             WHERE username=? AND problem_id=?
          ORDER BY id DESC
             LIMIT 1
            """,
            (username, problem_id),
        ).fetchone()
    if not row:
        return None
    return {k: row[k] for k in row.keys()}


def list_assignments(*, db_path: Path = DB_PATH) -> list[dict[str, Any]]:
    init_db(db_path)
    with get_conn(db_path) as conn:
        rows = conn.execute(
            """
            SELECT a.id,
                   a.title,
                   a.description,
                   a.created_at,
                   COALESCE(a.generation_status, '') AS generation_status,
                   COALESCE(a.generation_error, '') AS generation_error,
                   COALESCE(a.active, 0) AS active,
                   COALESCE(a.archived, 0) AS archived,
                   (SELECT COUNT(1) FROM test_cases t WHERE t.assignment_id=a.id AND t.visibility='visible') AS visible_tests,
                   (SELECT COUNT(1) FROM test_cases t WHERE t.assignment_id=a.id AND t.visibility='hidden') AS hidden_tests,
                   (SELECT COUNT(1) FROM test_cases t WHERE t.assignment_id=a.id AND t.visibility='stress') AS stress_tests
              FROM assignments a
          ORDER BY a.created_at DESC
            """
        ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        out.append({k: r[k] for k in r.keys()})
    return out


def get_assignment(*, assignment_id: str, db_path: Path = DB_PATH) -> dict[str, Any] | None:
    init_db(db_path)
    with get_conn(db_path) as conn:
        row = conn.execute(
            """
            SELECT id, title, description, created_at,
                   metadata_json, constraints_text, examples_json, difficulty, tags_json,
                   generated_description, input_format, output_format, examples_text,
                   reference_solution_lang, reference_solution_code,
                   COALESCE(generation_status, '') AS generation_status,
                   COALESCE(generation_error, '') AS generation_error,
                   COALESCE(active, 0) AS active,
                   COALESCE(archived, 0) AS archived
              FROM assignments
             WHERE id=?
            """,
            (assignment_id,),
        ).fetchone()
    if not row:
        return None
    return {k: row[k] for k in row.keys()}


def delete_test_case(*, test_case_id: int, db_path: Path = DB_PATH) -> None:
    init_db(db_path)
    with get_conn(db_path) as conn:
        conn.execute("DELETE FROM test_cases WHERE id=?", (int(test_case_id),))


def delete_all_test_cases(*, assignment_id: str, db_path: Path = DB_PATH) -> None:
    init_db(db_path)
    with get_conn(db_path) as conn:
        conn.execute("DELETE FROM test_cases WHERE assignment_id=?", (assignment_id,))


@dataclass(frozen=True)
class SubmissionRow:
    id: int
    student_name: str
    username: str
    phone: str | None
    problem_id: str
    language: str
    submission_path: str
    created_at: str


@dataclass(frozen=True)
class EvaluationRow:
    id: int
    submission_id: int
    status: str
    score: float
    report_path: str | None
    result_json_path: str | None
    error: str | None
    tool_results: list[dict[str, Any]]
    created_at: str
    finished_at: str | None


def create_submission(
    *,
    student_name: str,
    username: str,
    phone: str | None = None,
    problem_id: str,
    language: str,
    submission_path: Path,
    db_path: Path = DB_PATH,
) -> SubmissionRow:
    init_db(db_path)
    created_at = _utcnow_iso()
    with get_conn(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO submissions(student_name, username, phone, problem_id, language, submission_path, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (student_name, username, phone, problem_id, language, str(submission_path), created_at),
        )
        submission_id = int(cur.lastrowid)
    return SubmissionRow(
        id=submission_id,
        student_name=student_name,
        username=username,
        phone=phone,
        problem_id=problem_id,
        language=language,
        submission_path=str(submission_path),
        created_at=created_at,
    )


def get_submission(submission_id: int, db_path: Path = DB_PATH) -> dict[str, Any] | None:
    init_db(db_path)
    with get_conn(db_path) as conn:
        row = conn.execute("SELECT * FROM submissions WHERE id=?", (int(submission_id),)).fetchone()
    return {k: row[k] for k in row.keys()} if row else None


def delete_submission(*, submission_id: int, db_path: Path = DB_PATH) -> None:
    """Delete a submission row. Cascades to evaluations via FK."""
    init_db(db_path)
    with get_conn(db_path) as conn:
        conn.execute("DELETE FROM submissions WHERE id=?", (int(submission_id),))


def create_evaluation(*, submission_id: int, db_path: Path = DB_PATH) -> EvaluationRow:
    init_db(db_path)
    created_at = _utcnow_iso()
    with get_conn(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO evaluations(submission_id, status, score, tool_results_json, created_at)
            VALUES (?, 'queued', 0, '[]', ?)
            """,
            (submission_id, created_at),
        )
        evaluation_id = int(cur.lastrowid)
    return EvaluationRow(
        id=evaluation_id,
        submission_id=submission_id,
        status="queued",
        score=0.0,
        report_path=None,
        result_json_path=None,
        error=None,
        tool_results=[],
        created_at=created_at,
        finished_at=None,
    )


def update_evaluation_running(*, evaluation_id: int, db_path: Path = DB_PATH) -> None:
    with get_conn(db_path) as conn:
        conn.execute("UPDATE evaluations SET status='running' WHERE id=?", (evaluation_id,))


def update_evaluation_finished(
    *,
    evaluation_id: int,
    status: str,
    score: float,
    report_path: Path | None,
    result_json_path: Path | None,
    tool_results: list[dict[str, Any]],
    error: str | None = None,
    db_path: Path = DB_PATH,
) -> None:
    finished_at = _utcnow_iso()
    with get_conn(db_path) as conn:
        conn.execute(
            """
            UPDATE evaluations
               SET status=?,
                   score=?,
                   report_path=?,
                   result_json_path=?,
                   error=?,
                   tool_results_json=?,
                   finished_at=?
             WHERE id=?
            """,
            (
                status,
                float(score),
                str(report_path) if report_path else None,
                str(result_json_path) if result_json_path else None,
                error,
                json.dumps(tool_results),
                finished_at,
                evaluation_id,
            ),
        )


def list_recent_evaluations(limit: int = 50, db_path: Path = DB_PATH) -> list[dict[str, Any]]:
    init_db(db_path)
    with get_conn(db_path) as conn:
        rows = conn.execute(
            """
            SELECT e.id as evaluation_id,
                   e.status,
                   e.score,
                   e.report_path,
                   e.result_json_path,
                   e.error,
                   e.created_at,
                   e.finished_at,
                   s.student_name,
                   s.username,
                   s.phone,
                   s.problem_id,
                   s.language
              FROM evaluations e
              JOIN submissions s ON s.id = e.submission_id
          ORDER BY e.id DESC
             LIMIT ?
            """,
            (int(limit),),
        ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        out.append({k: r[k] for k in r.keys()})
    return out


def list_evaluations_for_user(username: str, limit: int = 50, db_path: Path = DB_PATH) -> list[dict[str, Any]]:
    init_db(db_path)
    with get_conn(db_path) as conn:
        rows = conn.execute(
            """
            SELECT e.id as evaluation_id,
                   e.status,
                   e.score,
                   e.report_path,
                   e.result_json_path,
                   e.error,
                   e.created_at,
                   e.finished_at,
                   s.id as submission_id,
                   s.student_name,
                   s.username,
                   s.phone,
                   s.problem_id,
                   s.language
              FROM evaluations e
              JOIN submissions s ON s.id = e.submission_id
             WHERE s.username = ?
          ORDER BY e.id DESC
             LIMIT ?
            """,
            (username, int(limit)),
        ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        out.append({k: r[k] for k in r.keys()})
    return out


def get_evaluation(evaluation_id: int, db_path: Path = DB_PATH) -> EvaluationRow | None:
    init_db(db_path)
    with get_conn(db_path) as conn:
        row = conn.execute("SELECT * FROM evaluations WHERE id=?", (int(evaluation_id),)).fetchone()
    if not row:
        return None
    try:
        tool_results = json.loads(row["tool_results_json"] or "[]")
    except json.JSONDecodeError:
        tool_results = []
    return EvaluationRow(
        id=int(row["id"]),
        submission_id=int(row["submission_id"]),
        status=str(row["status"]),
        score=float(row["score"] or 0.0),
        report_path=row["report_path"],
        result_json_path=row["result_json_path"],
        error=row["error"],
        tool_results=tool_results if isinstance(tool_results, list) else [],
        created_at=str(row["created_at"]),
        finished_at=row["finished_at"],
    )


def list_active_assignments(*, db_path: Path = DB_PATH) -> list[dict[str, Any]]:
    init_db(db_path)
    with get_conn(db_path) as conn:
        rows = conn.execute(
            """
            SELECT a.id,
                   a.title,
                   a.description,
                   a.created_at,
                   COALESCE(a.difficulty, '') AS difficulty,
                   COALESCE(a.generation_status, '') AS generation_status,
                   COALESCE(a.active, 0) AS active,
                   (SELECT COUNT(1) FROM test_cases t WHERE t.assignment_id=a.id AND t.visibility='visible') AS visible_tests,
                   (SELECT COUNT(1) FROM test_cases t WHERE t.assignment_id=a.id AND t.visibility='hidden') AS hidden_tests,
                   (SELECT COUNT(1) FROM test_cases t WHERE t.assignment_id=a.id AND t.visibility='stress') AS stress_tests
              FROM assignments a
             WHERE COALESCE(a.active, 0) = 1
               AND COALESCE(a.archived, 0) = 0
          ORDER BY a.created_at DESC
            """
        ).fetchall()
    return [{k: r[k] for k in r.keys()} for r in rows]


def list_student_assignments(*, db_path: Path = DB_PATH) -> list[dict[str, Any]]:
    """Assignments visible on the student side.

    Students should only see published (active) problems. Archived problems must be hidden.
    """
    init_db(db_path)
    with get_conn(db_path) as conn:
        rows = conn.execute(
            """
            SELECT a.id,
                   a.title,
                   a.description,
                   a.created_at,
                   COALESCE(a.difficulty, '') AS difficulty,
                   COALESCE(a.generation_status, '') AS generation_status,
                   COALESCE(a.generation_error, '') AS generation_error,
                   COALESCE(a.active, 0) AS active,
                   COALESCE(a.archived, 0) AS archived,
                   (SELECT COUNT(1) FROM test_cases t WHERE t.assignment_id=a.id AND t.visibility='visible') AS visible_tests,
                   (SELECT COUNT(1) FROM test_cases t WHERE t.assignment_id=a.id AND t.visibility='hidden') AS hidden_tests,
                   (SELECT COUNT(1) FROM test_cases t WHERE t.assignment_id=a.id AND t.visibility='stress') AS stress_tests
              FROM assignments a
             WHERE COALESCE(a.active, 0) = 1
               AND COALESCE(a.archived, 0) = 0
          ORDER BY a.created_at DESC
            """
        ).fetchall()
    return [{k: r[k] for k in r.keys()} for r in rows]


def set_assignment_active(*, assignment_id: str, active: bool, db_path: Path = DB_PATH) -> None:
    init_db(db_path)
    with get_conn(db_path) as conn:
        conn.execute("UPDATE assignments SET active=? WHERE id=?", (1 if active else 0, assignment_id))


def set_assignment_archived(*, assignment_id: str, archived: bool, db_path: Path = DB_PATH) -> None:
    init_db(db_path)
    with get_conn(db_path) as conn:
        if archived:
            conn.execute("UPDATE assignments SET archived=1, active=0 WHERE id=?", (assignment_id,))
        else:
            conn.execute("UPDATE assignments SET archived=0 WHERE id=?", (assignment_id,))


def create_user(
    *,
    username: str,
    email: str,
    password_hash: str,
    phone: str | None = None,
    role: str = "student",
    db_path: Path = DB_PATH,
) -> int:
    init_db(db_path)
    created_at = _utcnow_iso()
    u = (username or "").strip().lower()
    e = (email or "").strip().lower()
    r = (role or "student").strip().lower()
    if r not in {"student", "instructor", "admin"}:
        r = "student"
    with get_conn(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO users(username, email, password_hash, phone, role, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (u, e, password_hash, phone, r, created_at),
        )
        return int(cur.lastrowid)


def get_user_by_username(username: str, db_path: Path = DB_PATH) -> dict[str, Any] | None:
    init_db(db_path)
    u = (username or "").strip().lower()
    with get_conn(db_path) as conn:
        row = conn.execute("SELECT * FROM users WHERE username=?", (u,)).fetchone()
    return {k: row[k] for k in row.keys()} if row else None


def get_user_by_email(email: str, db_path: Path = DB_PATH) -> dict[str, Any] | None:
    init_db(db_path)
    e = (email or "").strip().lower()
    with get_conn(db_path) as conn:
        row = conn.execute("SELECT * FROM users WHERE email=?", (e,)).fetchone()
    return {k: row[k] for k in row.keys()} if row else None


def get_user_by_id(user_id: int, db_path: Path = DB_PATH) -> dict[str, Any] | None:
    init_db(db_path)
    with get_conn(db_path) as conn:
        row = conn.execute("SELECT * FROM users WHERE id=?", (int(user_id),)).fetchone()
    return {k: row[k] for k in row.keys()} if row else None


def count_users(db_path: Path = DB_PATH) -> int:
    init_db(db_path)
    with get_conn(db_path) as conn:
        row = conn.execute("SELECT COUNT(1) AS c FROM users").fetchone()
    return int(row["c"] or 0) if row else 0


def enqueue_job(*, job_type: str, payload: dict[str, Any], db_path: Path = DB_PATH) -> int:
    init_db(db_path)
    created_at = _utcnow_iso()
    with get_conn(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO jobs(type, payload_json, status, created_at, updated_at)
            VALUES (?, ?, 'queued', ?, ?)
            """,
            (str(job_type), json.dumps(payload or {}), created_at, created_at),
        )
        return int(cur.lastrowid)


def get_job(job_id: int, db_path: Path = DB_PATH) -> dict[str, Any] | None:
    init_db(db_path)
    with get_conn(db_path) as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id=?", (int(job_id),)).fetchone()
    if not row:
        return None
    out = {k: row[k] for k in row.keys()}
    try:
        out["payload"] = json.loads(out.get("payload_json") or "{}")
    except Exception:
        out["payload"] = {}
    try:
        out["result"] = json.loads(out.get("result_json") or "{}") if out.get("result_json") else None
    except Exception:
        out["result"] = None
    return out


def claim_next_job(*, db_path: Path = DB_PATH, types: list[str] | None = None) -> dict[str, Any] | None:
    init_db(db_path)
    now = _utcnow_iso()
    with get_conn(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        if types:
            placeholders = ",".join(["?"] * len(types))
            row = conn.execute(
                f"SELECT * FROM jobs WHERE status='queued' AND type IN ({placeholders}) ORDER BY id ASC LIMIT 1",
                tuple(types),
            ).fetchone()
        else:
            row = conn.execute("SELECT * FROM jobs WHERE status='queued' ORDER BY id ASC LIMIT 1").fetchone()

        if not row:
            conn.execute("ROLLBACK")
            return None

        jid = int(row["id"])
        cur = conn.execute(
            "UPDATE jobs SET status='running', updated_at=? WHERE id=? AND status='queued'",
            (now, jid),
        )
        if cur.rowcount != 1:
            conn.execute("ROLLBACK")
            return None

        conn.execute("COMMIT")

        out = {k: row[k] for k in row.keys()}
        try:
            out["payload"] = json.loads(out.get("payload_json") or "{}")
        except Exception:
            out["payload"] = {}
        return out


def update_job_finished(
    *,
    job_id: int,
    status: str,
    error: str | None = None,
    result: dict[str, Any] | None = None,
    db_path: Path = DB_PATH,
) -> None:
    init_db(db_path)
    now = _utcnow_iso()
    st = (status or "").strip().lower()
    if st not in {"completed", "failed"}:
        st = "failed"
    with get_conn(db_path) as conn:
        conn.execute(
            """
            UPDATE jobs
               SET status=?,
                   error=?,
                   result_json=?,
                   updated_at=?
             WHERE id=?
            """,
            (st, error, json.dumps(result) if result is not None else None, now, int(job_id)),
        )


