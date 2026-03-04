"""Batch evaluation and dashboard generation for all student submissions."""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class BatchRow:
    github_username: str
    student_name: str
    email: str
    problem_id: str
    language: str
    submission_file: str
    anti_cheat: str
    plagiarism: str
    total_test_cases: int
    passed_cases: int
    visible_passed: str
    hidden_passed: str
    score: float
    attempts: int
    plagiarism_hits: int
    last_attempt_utc: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate batch dashboard for all submissions.")
    parser.add_argument("--submissions-dir", default="submissions", help="Directory with student submissions")
    parser.add_argument("--students-file", default="students.csv", help="Student mapping CSV path")
    parser.add_argument("--output-dir", default="results/batch", help="Output directory for batch reports")
    parser.add_argument("--attempt-history", default="results/attempt_history.jsonl", help="Path to attempt history jsonl")
    return parser.parse_args()


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


def find_submission_files(submissions_dir: Path) -> list[tuple[str, Path]]:
    pairs: list[tuple[str, Path]] = []
    if not submissions_dir.exists():
        return pairs

    for student_dir in sorted(p for p in submissions_dir.iterdir() if p.is_dir()):
        code_files = sorted(list(student_dir.rglob("*.py")) + list(student_dir.rglob("*.java")))
        if not code_files:
            continue
        # Use the most recently modified file as current submission.
        latest = max(code_files, key=lambda p: p.stat().st_mtime)
        pairs.append((student_dir.name, latest))
    return pairs


def parse_result_file(result_file: Path) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for line in result_file.read_text(encoding="utf-8").splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        parsed[key.strip()] = value.strip()
    return parsed


def load_attempt_history(history_file: Path) -> dict[str, dict[str, str | int]]:
    stats: dict[str, dict[str, str | int]] = {}
    if not history_file.exists():
        return stats

    for line in history_file.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw:
            continue
        try:
            rec = json.loads(raw)
        except json.JSONDecodeError:
            continue

        username = str(rec.get("username", "")).strip()
        if not username:
            continue

        entry = stats.setdefault(
            username,
            {
                "attempts": 0,
                "plagiarism_hits": 0,
                "last_attempt_utc": "",
            },
        )
        entry["attempts"] = int(entry["attempts"]) + 1
        if bool(rec.get("plagiarism_detected", False)):
            entry["plagiarism_hits"] = int(entry["plagiarism_hits"]) + 1
        ts = str(rec.get("timestamp_utc", ""))
        if ts and ts > str(entry["last_attempt_utc"]):
            entry["last_attempt_utc"] = ts

    return stats


def run_single_evaluation(submission_file: Path, student_name: str, result_file: Path) -> None:
    cmd = [
        sys.executable,
        "evaluator.py",
        str(submission_file),
        "--student-name",
        student_name,
        "--result-file",
        str(result_file),
    ]
    process = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if process.stdout:
        print(process.stdout.strip())
    if process.stderr:
        print(process.stderr.strip())
    if process.returncode != 0:
        raise RuntimeError(f"Evaluation failed for {submission_file}")


def write_csv(rows: list[BatchRow], csv_path: Path) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(asdict(rows[0]).keys()) if rows else list(BatchRow.__annotations__.keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))


def write_json(rows: list[BatchRow], json_path: Path) -> None:
    payload = [asdict(row) for row in rows]
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_dashboard_markdown(rows: list[BatchRow], md_path: Path) -> None:
    md_path.parent.mkdir(parents=True, exist_ok=True)
    total = len(rows)
    passed = sum(1 for row in rows if row.score >= 80.0 and row.anti_cheat == "PASS")
    avg = round(sum(row.score for row in rows) / total, 2) if total else 0.0

    plagiarism_total = sum(1 for row in rows if row.plagiarism == "DETECTED")
    anti_cheat_failures = sum(1 for row in rows if row.anti_cheat != "PASS")

    lines = [
        "# Batch Evaluation Dashboard",
        "",
        f"- Total submissions: {total}",
        f"- Passed threshold (>=80 and anti-cheat PASS): {passed}",
        f"- Average score: {avg}",
        f"- Anti-cheat failures: {anti_cheat_failures}",
        f"- Plagiarism detected: {plagiarism_total}",
        "",
        "| GitHub Username | Problem | Lang | Anti-Cheat | Plagiarism | Attempts | Passed Cases | Score |",
        "|---|---|---|---|---|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row.github_username} | {row.problem_id} | {row.language} | {row.anti_cheat} | "
            f"{row.plagiarism} | {row.attempts} | {row.passed_cases}/{row.total_test_cases} | {row.score} |"
        )

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    submissions_dir = Path(args.submissions_dir).resolve()
    students_file = Path(args.students_file).resolve()
    output_dir = Path(args.output_dir).resolve()
    history_file = Path(args.attempt_history).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    students_map = load_students_map(students_file)
    history_stats = load_attempt_history(history_file)
    submissions = find_submission_files(submissions_dir)
    if not submissions:
        print("No submissions found for batch reporting.")
        return 1

    rows: list[BatchRow] = []
    for username, submission_file in submissions:
        mapped_name, mapped_email = students_map.get(username, (username, ""))
        result_file = output_dir / f"{username}_result.txt"
        run_single_evaluation(submission_file=submission_file, student_name=mapped_name, result_file=result_file)
        parsed = parse_result_file(result_file)
        stats = history_stats.get(username, {"attempts": 0, "plagiarism_hits": 0, "last_attempt_utc": ""})

        row = BatchRow(
            github_username=username,
            student_name=parsed.get("Student Name", mapped_name),
            email=mapped_email,
            problem_id=parsed.get("Problem ID", "add_numbers"),
            language=parsed.get("Language", submission_file.suffix.lower().lstrip(".")),
            submission_file=str(submission_file.relative_to(Path.cwd())),
            anti_cheat=parsed.get("Anti-Cheat", "UNKNOWN"),
            plagiarism=parsed.get("Plagiarism", "NOT_DETECTED"),
            total_test_cases=int(parsed.get("Total Test Cases", "0")),
            passed_cases=int(parsed.get("Passed Cases", "0")),
            visible_passed=parsed.get("Visible Passed", "0/0"),
            hidden_passed=parsed.get("Hidden Passed", "0/0"),
            score=float(parsed.get("Score", "0")),
            attempts=int(stats["attempts"]),
            plagiarism_hits=int(stats["plagiarism_hits"]),
            last_attempt_utc=str(stats["last_attempt_utc"]),
        )
        rows.append(row)

    csv_path = output_dir / "batch_report.csv"
    json_path = output_dir / "batch_report.json"
    md_path = output_dir / "dashboard.md"

    write_csv(rows, csv_path)
    write_json(rows, json_path)
    write_dashboard_markdown(rows, md_path)

    print(f"Batch report generated for {len(rows)} submission(s).")
    print(f"CSV: {csv_path}")
    print(f"JSON: {json_path}")
    print(f"Dashboard: {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
