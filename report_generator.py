"""Reporting utilities for assignment evaluation."""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path


def append_marks_to_csv(name: str, score: float, csv_file: str | Path = "results/marks.csv") -> Path:
    """Append one student's marks to a CSV file, creating it with headers if needed."""
    if not name or not name.strip():
        raise ValueError("name must be a non-empty string")

    file_path = Path(csv_file)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    write_header = not file_path.exists() or file_path.stat().st_size == 0

    with file_path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        if write_header:
            writer.writerow(["Name", "Score", "Date"])
        writer.writerow([name.strip(), score, date.today().isoformat()])

    return file_path
