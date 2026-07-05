from __future__ import annotations

import argparse
import json
from pathlib import Path

from evaluation.multi_agent_runner import run_local_multi_agent, save_report


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run local multi-agent evaluation (no OpenAI, uses local MCP endpoints).")
    p.add_argument("submission_path")
    p.add_argument("--student-name", required=True)
    p.add_argument("--problem-id", required=True)
    p.add_argument("--language", required=True, choices=["python", "java", "javascript", "cpp"])
    p.add_argument("--out", default="results/agent_report.json")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    submission = {
        "student_name": args.student_name,
        "problem_id": args.problem_id,
        "language": args.language,
        "submission_path": str(Path(args.submission_path).resolve()),
    }
    report = run_local_multi_agent(submission=submission)
    out_path = save_report(report, Path(args.out))
    print(f"Wrote: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

