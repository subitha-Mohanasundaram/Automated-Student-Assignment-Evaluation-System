from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path

import evaluator


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Batch evaluate submissions in a folder.")
    p.add_argument("submissions_folder", help="Folder to scan for submissions")
    p.add_argument("--out-dir", default=None, help="Output dir (default: results/batch/<timestamp>)")
    p.add_argument("--problem-id", default=None, help="Force problem id for all submissions (optional)")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.submissions_folder).resolve()
    if not root.exists():
        print(f"Not found: {root}")
        return 1

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(args.out_dir).resolve() if args.out_dir else (Path("results") / "batch" / ts)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, object]] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".py", ".java", ".js", ".cpp"}:
            continue

        problem_id = args.problem_id.strip() if args.problem_id else evaluator._infer_problem_id(path)  # type: ignore[attr-defined]
        student_name = evaluator._infer_username(path)  # type: ignore[attr-defined]
        result_file = out_dir / f"{student_name}_{problem_id}{path.suffix}.txt"

        code = evaluator.evaluate_student(
            student_file=path,
            student_name=student_name,
            result_file=result_file,
            problem_id=problem_id,
        )
        result_json = result_file.with_suffix(".json")
        score = 0.0
        status = "completed" if code == 0 else "failed"
        if result_json.exists():
            try:
                obj = json.loads(result_json.read_text(encoding="utf-8"))
                score = float(obj.get("score", 0.0) or 0.0)
                status = "completed"
            except Exception:
                pass

        rows.append(
            {
                "student": student_name,
                "problem_id": problem_id,
                "language": path.suffix.lower().lstrip("."),
                "status": status,
                "score": score,
                "result_txt": str(result_file),
                "result_json": str(result_json) if result_json.exists() else "",
            }
        )

    summary_path = out_dir / "batch_report.json"
    summary_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")

    csv_path = out_dir / "batch_report.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["student", "problem_id", "language", "status", "score", "result_txt", "result_json"],
        )
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in w.fieldnames})

    print(f"Wrote: {summary_path}")
    print(f"Wrote: {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

