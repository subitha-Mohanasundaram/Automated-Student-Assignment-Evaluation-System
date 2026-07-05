"""CLI utilities to manage assignments and IO-style test cases in the platform DB.

This is intentionally minimal: it enables coding-interview style evaluation where student programs
read stdin and write stdout, and are graded against input/expected-output test cases.
"""

from __future__ import annotations

import argparse

from assignment_intel.db import add_test_case, list_test_cases, upsert_assignment


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Manage assignments + test cases (SQLite).")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("create", help="Create or update an assignment")
    c.add_argument("--id", required=True, help="Assignment id (used as problem_id)")
    c.add_argument("--title", required=True)
    c.add_argument("--description", default="")

    t = sub.add_parser("add-test", help="Add an IO test case (stdin -> expected stdout)")
    t.add_argument("--id", required=True, help="Assignment id")
    t.add_argument("--input", required=True, help="Input text (use \\n for newlines)")
    t.add_argument("--expected", required=True, help="Expected output text")
    t.add_argument("--visibility", default="visible", choices=["visible", "hidden", "stress"])
    t.add_argument("--weight", type=float, default=1.0)

    l = sub.add_parser("list", help="List test cases for an assignment")
    l.add_argument("--id", required=True)

    return p.parse_args()


def main() -> int:
    args = parse_args()
    if args.cmd == "create":
        upsert_assignment(assignment_id=args.id, title=args.title, description=args.description)
        print(f"OK: assignment upserted: {args.id}")
        return 0

    if args.cmd == "add-test":
        add_test_case(
            assignment_id=args.id,
            input_text=str(args.input).encode("utf-8").decode("unicode_escape"),
            expected_output=args.expected,
            visibility=args.visibility,
            weight=float(args.weight),
        )
        print(f"OK: test case added to: {args.id}")
        return 0

    if args.cmd == "list":
        rows = list_test_cases(assignment_id=args.id)
        for r in rows:
            print(f"[{r['id']}] {r['visibility']} w={r['weight']} input={r['input_text']!r} expected={r['expected_output']!r}")
        return 0

    raise SystemExit("unknown command")


if __name__ == "__main__":
    raise SystemExit(main())
