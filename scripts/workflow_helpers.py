"""Helpers for GitHub Actions workflow metadata resolution."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class StudentResolution:
    actor: str
    name: str
    email: str
    mapped: bool


def resolve_student_details(students_file: Path, actor: str, admin_email: str | None) -> StudentResolution:
    actor_clean = actor.strip()
    if not actor_clean:
        raise ValueError("actor must not be empty")

    if students_file.exists():
        with students_file.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                username = (row.get("github_username") or "").strip()
                if username != actor_clean:
                    continue
                name = (row.get("student_name") or actor_clean).strip() or actor_clean
                email = (row.get("email") or "").strip()
                if not email:
                    raise ValueError(f"Email is empty for mapped GitHub user: {actor_clean}")
                return StudentResolution(actor=actor_clean, name=name, email=email, mapped=True)

    fallback = (admin_email or "").strip()
    if not fallback:
        raise ValueError(f"No mapping for {actor_clean} and ADMIN_EMAIL fallback is empty")
    return StudentResolution(actor=actor_clean, name=actor_clean, email=fallback, mapped=False)


def write_github_output(resolution: StudentResolution, github_output_path: Path) -> None:
    with github_output_path.open("a", encoding="utf-8") as handle:
        handle.write(f"name={resolution.name}\n")
        handle.write(f"email={resolution.email}\n")
        handle.write(f"actor={resolution.actor}\n")
        handle.write(f"mapped={'true' if resolution.mapped else 'false'}\n")


def write_unmapped_csv(
    *,
    output_file: Path,
    resolution: StudentResolution,
    workflow_run_id: str,
    workflow_url: str,
) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    header = "github_username,detected_at_utc,workflow_run_id,workflow_url"
    row = f"{resolution.actor},{timestamp},{workflow_run_id},{workflow_url}"
    output_file.write_text(f"{header}\n{row}\n", encoding="utf-8")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Workflow helper utilities")
    sub = parser.add_subparsers(dest="command", required=True)

    resolve = sub.add_parser("resolve", help="Resolve actor to student identity/email")
    resolve.add_argument("--students-file", required=True)
    resolve.add_argument("--actor", required=True)
    resolve.add_argument("--admin-email", default="")
    resolve.add_argument("--github-output", required=True)
    resolve.add_argument("--unmapped-csv", default="")
    resolve.add_argument("--workflow-run-id", default="")
    resolve.add_argument("--workflow-url", default="")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.command != "resolve":
        return 1

    resolution = resolve_student_details(
        students_file=Path(args.students_file),
        actor=args.actor,
        admin_email=args.admin_email,
    )
    write_github_output(resolution=resolution, github_output_path=Path(args.github_output))
    print(f"Resolved actor '{resolution.actor}' mapped={resolution.mapped} recipient={resolution.email}")

    if (not resolution.mapped) and args.unmapped_csv:
        if not args.workflow_run_id or not args.workflow_url:
            raise ValueError("workflow-run-id and workflow-url are required when unmapped-csv is provided")
        write_unmapped_csv(
            output_file=Path(args.unmapped_csv),
            resolution=resolution,
            workflow_run_id=args.workflow_run_id,
            workflow_url=args.workflow_url,
        )
        print(f"Wrote unmapped user artifact: {args.unmapped_csv}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
