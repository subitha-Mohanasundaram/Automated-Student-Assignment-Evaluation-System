"""Run submission evaluation locally as a self-hosted alternative to GitHub Actions."""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Self-hosted local runner for realtime submission evaluation.")
    parser.add_argument("submission_file", help="Path to student submission (.py or .java)")
    parser.add_argument("--student-name", default=None, help="Optional display name override")
    parser.add_argument("--problem-id", default=None, help="Optional problem id override")
    parser.add_argument("--students-file", default="students.csv", help="Student mapping CSV")
    parser.add_argument("--send-email", action="store_true", help="Send result email after evaluation")
    return parser.parse_args()


def infer_username(submission_file: Path) -> str:
    parts = submission_file.parts
    if "submissions" in parts:
        idx = parts.index("submissions")
        if idx + 1 < len(parts):
            return parts[idx + 1]
    return submission_file.stem


def load_students_map(students_file: Path) -> dict[str, tuple[str, str]]:
    if not students_file.exists():
        return {}
    mapping: dict[str, tuple[str, str]] = {}
    with students_file.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            username = (row.get("github_username") or "").strip()
            if not username:
                continue
            name = (row.get("student_name") or username).strip() or username
            email = (row.get("email") or "").strip()
            mapping[username] = (name, email)
    return mapping


def run_cmd(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).parent.resolve()
    submission_file = Path(args.submission_file).resolve()
    if not submission_file.exists():
        print(f"Error: submission file not found: {submission_file}")
        return 1

    username = infer_username(submission_file)
    students_map = load_students_map((repo_root / args.students_file).resolve())
    mapped_name, mapped_email = students_map.get(username, (username, ""))
    student_name = args.student_name.strip() if args.student_name else mapped_name

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = repo_root / "results" / "local_runs" / f"{username}_{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    result_file = run_dir / "result.txt"

    eval_cmd = [
        sys.executable,
        "evaluator.py",
        str(submission_file),
        "--student-name",
        student_name,
        "--result-file",
        str(result_file),
    ]
    if args.problem_id:
        eval_cmd.extend(["--problem-id", args.problem_id.strip()])

    eval_proc = run_cmd(eval_cmd)
    if eval_proc.stdout:
        print(eval_proc.stdout.strip())
    if eval_proc.stderr:
        print(eval_proc.stderr.strip())
    if eval_proc.returncode != 0:
        print("Evaluation failed.")
        return eval_proc.returncode

    result_json = result_file.with_suffix(".json")
    summary_md = run_dir / "summary.md"
    lines = [
        "# Local Evaluation Summary",
        "",
        f"- Submission: `{submission_file}`",
        f"- Username: `{username}`",
        f"- Student Name: `{student_name}`",
        f"- Result File: `{result_file}`",
        f"- Result JSON: `{result_json}`" if result_json.exists() else "- Result JSON: not generated",
    ]
    summary_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    if args.send_email:
        if not mapped_email:
            print(f"Email not sent: no recipient email found for username '{username}' in students.csv")
            return 1
        email_cmd = [
            sys.executable,
            "email_sender.py",
            mapped_email,
            "--student-name",
            student_name,
            "--result-file",
            str(result_file),
            "--subject",
            "Assignment Evaluation Result",
        ]
        email_proc = run_cmd(email_cmd)
        if email_proc.stdout:
            print(email_proc.stdout.strip())
        if email_proc.stderr:
            print(email_proc.stderr.strip())
        if email_proc.returncode != 0:
            print("Evaluation completed, but email failed.")
            return email_proc.returncode

    print(f"Self-hosted run completed: {run_dir}")
    if result_json.exists():
        try:
            payload = json.loads(result_json.read_text(encoding="utf-8"))
            print(f"Final score: {payload.get('score')}")
        except json.JSONDecodeError:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
