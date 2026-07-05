from __future__ import annotations

import contextlib
import io
import json
import re
from datetime import datetime
from pathlib import Path

from assignment_intel.complexity import estimate_python_complexity
from assignment_intel.ai_feedback import tool_ai_feedback
from assignment_intel.models import Submission, ToolResult
from assignment_intel.sandbox_runner import get_docker_image_for_language, get_sandbox_mode, run_in_docker


def _safe_slug(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = value.strip("_")
    return value or "student"


def tool_check_relevance(*, submission: Submission) -> ToolResult:
    """
    Best-effort semantic guardrail: verify the submitted code looks like an attempt for this problem.

    This is not the scoring mechanism. It only blocks obviously unrelated / placeholder submissions.
    Uses OpenAI when configured; falls back to simple heuristics offline.
    """
    from assignment_intel.db import get_assignment

    a = get_assignment(assignment_id=submission.problem_id)
    title = str(a.get("title") or "") if isinstance(a, dict) else ""
    desc = str(a.get("description") or "") if isinstance(a, dict) else ""
    gen_desc = str(a.get("generated_description") or "") if isinstance(a, dict) else ""
    input_fmt = str(a.get("input_format") or "") if isinstance(a, dict) else ""
    output_fmt = str(a.get("output_format") or "") if isinstance(a, dict) else ""

    try:
        code = Path(submission.submission_path).read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return ToolResult(tool="check_relevance", ok=False, error=f"read_error: {exc}", data={"relevant": False, "reason": "Could not read submission file."})

    # Strip comments + whitespace for quick checks.
    code_compact = "\n".join([ln for ln in code.splitlines() if ln.strip() and not ln.strip().startswith(("#", "//"))])
    too_short = len(code_compact.strip()) < 60
    has_todo = "todo" in code_compact.lower() or "implement" in code_compact.lower()

    require_io = bool(input_fmt.strip() or output_fmt.strip() or ("stdin" in (desc + gen_desc).lower()))
    lang = str(submission.language or "").lower()

    def _io_signals_present() -> bool:
        if not require_io:
            return True
        c = code_compact.lower()
        if lang == "python":
            return ("sys.stdin" in c) or ("input(" in c) or ("print(" in c)
        if lang == "java":
            return ("scanner" in c) or ("bufferedreader" in c) or ("system.in" in c) or ("system.out" in c)
        if lang in {"c", "cpp", "c++"}:
            return ("scanf" in c) or ("printf" in c) or ("cin" in c) or ("cout" in c)
        if lang in {"javascript", "js"}:
            return ("readfilesync(0" in c) or ("process.stdin" in c) or ("console.log" in c)
        return True

    # Offline heuristic block: empty/template submissions.
    if too_short or has_todo or not _io_signals_present():
        reason = "Submission looks like a placeholder or does not match expected IO pattern."
        return ToolResult(tool="check_relevance", ok=False, error="irrelevant_solution", data={"relevant": False, "confidence": 0.6, "reason": reason, "require_io": require_io})

    # If OpenAI configured, ask for a stronger semantic check.
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    provider = os.getenv("AI_PROVIDER", "").strip().lower()
    model = os.getenv("OPENAI_MODEL", "gpt-5").strip()
    if provider == "openai" and api_key:
        prompt = (
            "Decide if the student's code is a genuine attempt to solve the given programming problem.\n"
            "Return ONLY valid JSON with keys: relevant(boolean), confidence(number 0..1), reason(string).\n\n"
            f"Problem ID: {submission.problem_id}\n"
            f"Title: {title}\n"
            f"Description: {gen_desc or desc}\n"
            f"Input format: {input_fmt}\n"
            f"Output format: {output_fmt}\n"
            f"Language: {submission.language}\n\n"
            "Student code:\n"
            "```text\n"
            f"{code[:6000]}\n"
            "```\n"
        )
        timeout_s = 20
        try:
            timeout_s = int(os.getenv("OPENAI_TIMEOUT_S", "20").strip() or "20")
        except Exception:
            timeout_s = 20
        try:
            from openai import OpenAI  # type: ignore

            client = OpenAI(api_key=api_key)
            resp = client.responses.create(
                model=model,
                input=[{"role": "user", "content": prompt}],
                temperature=0.0,
                timeout=timeout_s,
            )
            out = getattr(resp, "output_text", "") or ""
            obj = json.loads(out.strip())
            if isinstance(obj, dict) and isinstance(obj.get("relevant"), bool):
                relevant = bool(obj.get("relevant"))
                conf = float(obj.get("confidence", 0.5) or 0.5)
                reason = str(obj.get("reason") or "")
                if not relevant:
                    return ToolResult(tool="check_relevance", ok=False, error="irrelevant_solution", data={"relevant": False, "confidence": conf, "reason": reason, "require_io": require_io})
                return ToolResult(tool="check_relevance", ok=True, data={"relevant": True, "confidence": conf, "reason": reason, "require_io": require_io})
        except Exception:
            # Fall back to heuristic pass if AI call fails.
            pass

    return ToolResult(tool="check_relevance", ok=True, data={"relevant": True, "confidence": 0.55, "reason": "Heuristic pass.", "require_io": require_io})


def tool_evaluate_submission(*, submission: Submission) -> ToolResult:
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    username = _safe_slug(submission.student_name)
    result_dir = Path("results") / "single"
    result_dir.mkdir(parents=True, exist_ok=True)
    result_file = result_dir / f"{username}_{submission.problem_id}_{timestamp}.txt"

    sandbox_mode = get_sandbox_mode()
    if sandbox_mode == "docker":
        repo_root = Path(__file__).resolve().parent.parent
        try:
            student_rel = submission.submission_path.resolve().relative_to(repo_root)
            result_rel = result_file.resolve().relative_to(repo_root)
        except Exception as exc:
            return ToolResult(tool="evaluate_submission", ok=False, error=f"path_error: {exc}")

        image = get_docker_image_for_language(submission.language)
        cmd = [
            "python",
            "evaluator.py",
            str(student_rel).replace("\\", "/"),
            "--student-name",
            submission.student_name,
            "--result-file",
            str(result_rel).replace("\\", "/"),
            "--problem-id",
            submission.problem_id,
        ]
        if submission.extra_hidden_cases_path:
            try:
                extra_rel = submission.extra_hidden_cases_path.resolve().relative_to(repo_root)
                cmd.extend(["--extra-hidden-cases", str(extra_rel).replace("\\", "/")])
            except Exception as exc:
                return ToolResult(tool="evaluate_submission", ok=False, error=f"extra_cases_path_error: {exc}")
        sand = run_in_docker(repo_root=repo_root, image=image, command=cmd, timeout_s=120)
        json_path = result_file.with_suffix(".json")
        if not sand.ok or not json_path.exists():
            return ToolResult(
                tool="evaluate_submission",
                ok=False,
                error=sand.error or "docker_evaluation_failed",
                data={
                    "result_file": str(result_file),
                    "expected_result_json": str(json_path),
                    "exit_code": sand.exit_code,
                    "stdout": sand.stdout,
                    "stderr": sand.stderr,
                },
            )
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            return ToolResult(tool="evaluate_submission", ok=False, error=f"bad_result_json: {exc}")
        data["result_file"] = str(result_file)
        data["result_json"] = str(json_path)
        data["stdout"] = sand.stdout
        data["stderr"] = sand.stderr
        return ToolResult(tool="evaluate_submission", ok=True, data=data)

    try:
        import evaluator  # local module
    except Exception as exc:  # pragma: no cover
        return ToolResult(tool="evaluate_submission", ok=False, error=f"import_error: {exc}")

    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(stdout_buf), contextlib.redirect_stderr(stderr_buf):
            exit_code = evaluator.evaluate_student(
                student_file=submission.submission_path,
                student_name=submission.student_name,
                result_file=result_file,
                problem_id=submission.problem_id,
                extra_hidden_cases_path=submission.extra_hidden_cases_path,
            )
    except Exception as exc:
        return ToolResult(
            tool="evaluate_submission",
            ok=False,
            error=str(exc),
            data={"stdout": stdout_buf.getvalue(), "stderr": stderr_buf.getvalue()},
        )

    json_path = result_file.with_suffix(".json")
    if exit_code != 0 or not json_path.exists():
        return ToolResult(
            tool="evaluate_submission",
            ok=False,
            error="evaluation_failed",
            data={
                "result_file": str(result_file),
                "expected_result_json": str(json_path),
                "stdout": stdout_buf.getvalue(),
                "stderr": stderr_buf.getvalue(),
            },
        )

    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return ToolResult(tool="evaluate_submission", ok=False, error=f"bad_result_json: {exc}")

    data["result_file"] = str(result_file)
    data["result_json"] = str(json_path)
    data["stdout"] = stdout_buf.getvalue()
    data["stderr"] = stderr_buf.getvalue()
    return ToolResult(tool="evaluate_submission", ok=True, data=data)


def tool_analyze_complexity(*, submission: Submission) -> ToolResult:
    try:
        if submission.language.lower() != "python":
            return ToolResult(tool="analyze_complexity", ok=True, data={"time_complexity": "unknown", "space_complexity": "unknown"})
        estimate = estimate_python_complexity(submission.submission_path)
        return ToolResult(
            tool="analyze_complexity",
            ok=True,
            data={
                "time_complexity": estimate.time_complexity,
                "space_complexity": estimate.space_complexity,
                "notes": estimate.notes,
            },
        )
    except (OSError, SyntaxError, ValueError) as exc:
        return ToolResult(tool="analyze_complexity", ok=False, error=str(exc))


def tool_ai_feedback_wrapper(*, submission: Submission, eval_results: dict | None = None) -> ToolResult:
    return tool_ai_feedback(submission=submission, eval_results=eval_results or {})
