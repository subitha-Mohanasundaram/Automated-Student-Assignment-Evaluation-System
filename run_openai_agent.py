from __future__ import annotations

import argparse
import json
from pathlib import Path

from assignment_intel.openai_mcp_agent import run_openai_agent


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run OpenAI agent that uses MCP tools to evaluate a submission.")
    p.add_argument("submission_path", help="Path to the submission file")
    p.add_argument("--student-name", required=True)
    p.add_argument("--problem-id", required=True)
    p.add_argument("--language", required=True, choices=["python", "java", "javascript", "cpp"])
    p.add_argument("--out", default="results/agent_report.json", help="Output JSON file")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    result = run_openai_agent(
        student_name=args.student_name,
        problem_id=args.problem_id,
        language=args.language,
        submission_path=Path(args.submission_path),
    )

    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"Wrote: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

