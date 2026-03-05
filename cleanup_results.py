"""Cleanup utility for result retention and attempt history pruning."""

from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path


@dataclass
class CleanupStats:
    history_before: int = 0
    history_after: int = 0
    history_removed: int = 0
    local_run_dirs_removed: int = 0
    batch_files_removed: int = 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prune old results and attempt history.")
    parser.add_argument("--repo-root", default=".", help="Repository root path")
    parser.add_argument("--history-days", type=int, default=90, help="Keep attempt history for N days")
    parser.add_argument("--local-run-days", type=int, default=30, help="Keep local run folders for N days")
    parser.add_argument("--batch-days", type=int, default=30, help="Keep batch output files for N days")
    parser.add_argument("--report-file", default="results/cleanup_report.txt", help="Cleanup report output path")
    return parser.parse_args()


def _parse_ts(raw: str) -> datetime | None:
    text = raw.strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def prune_attempt_history(history_path: Path, keep_days: int, stats: CleanupStats) -> None:
    if not history_path.exists():
        return
    cutoff = datetime.now(timezone.utc) - timedelta(days=keep_days)
    kept: list[str] = []
    for line in history_path.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw:
            continue
        stats.history_before += 1
        try:
            rec = json.loads(raw)
        except json.JSONDecodeError:
            continue
        ts = _parse_ts(str(rec.get("timestamp_utc", "")))
        if ts is None or ts >= cutoff:
            kept.append(json.dumps(rec))

    stats.history_after = len(kept)
    stats.history_removed = max(stats.history_before - stats.history_after, 0)
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text(("\n".join(kept) + "\n") if kept else "", encoding="utf-8")


def prune_path_by_mtime(target: Path, keep_days: int, stats_attr: str, is_dir: bool) -> None:
    if not target.exists():
        return
    cutoff = datetime.now(timezone.utc) - timedelta(days=keep_days)
    removed = 0
    for item in target.iterdir():
        mtime = datetime.fromtimestamp(item.stat().st_mtime, tz=timezone.utc)
        if mtime >= cutoff:
            continue
        if is_dir and item.is_dir():
            shutil.rmtree(item, ignore_errors=True)
            removed += 1
        elif (not is_dir) and item.is_file():
            item.unlink(missing_ok=True)
            removed += 1
    setattr(stats, stats_attr, getattr(stats, stats_attr) + removed)


def write_report(report_path: Path, stats: CleanupStats) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report = (
        "Cleanup Summary\n"
        "===============\n"
        f"history_before={stats.history_before}\n"
        f"history_after={stats.history_after}\n"
        f"history_removed={stats.history_removed}\n"
        f"local_run_dirs_removed={stats.local_run_dirs_removed}\n"
        f"batch_files_removed={stats.batch_files_removed}\n"
    )
    report_path.write_text(report, encoding="utf-8")


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    stats = CleanupStats()

    prune_attempt_history(repo_root / "results" / "attempt_history.jsonl", args.history_days, stats)
    prune_path_by_mtime(repo_root / "results" / "local_runs", args.local_run_days, "local_run_dirs_removed", True)
    prune_path_by_mtime(repo_root / "results" / "batch", args.batch_days, "batch_files_removed", False)
    write_report((repo_root / args.report_file).resolve(), stats)

    print(f"Cleanup complete. History removed: {stats.history_removed}")
    print(f"Local run dirs removed: {stats.local_run_dirs_removed}")
    print(f"Batch files removed: {stats.batch_files_removed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
