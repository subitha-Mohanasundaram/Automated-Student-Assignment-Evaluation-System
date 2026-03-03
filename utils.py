"""Helper utilities for evaluation workflows."""

from __future__ import annotations

import difflib
import json
from pathlib import Path
from typing import Dict, List, Tuple


def calculate_score(obtained_points: List[float], max_points: List[float]) -> Tuple[float, float]:
    """Return total obtained score and maximum possible score."""
    if len(obtained_points) != len(max_points):
        raise ValueError("obtained_points and max_points must have same length")

    score = float(sum(obtained_points))
    max_score = float(sum(max_points))
    return score, max_score


def load_test_cases(path: Path) -> List[Dict]:
    """Load test cases from a JSON file."""
    if not path.exists():
        raise FileNotFoundError(f"Test case file not found: {path}")

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def check_plagiarism(file_one: str | Path, file_two: str | Path, threshold: float = 80.0) -> Tuple[float, bool]:
    """Compare two Python files and return similarity percentage and plagiarism flag.

    A submission is flagged when similarity is greater than the threshold.
    """
    path_one = Path(file_one)
    path_two = Path(file_two)

    if not path_one.exists() or not path_one.is_file():
        raise FileNotFoundError(f"First file not found: {path_one}")
    if not path_two.exists() or not path_two.is_file():
        raise FileNotFoundError(f"Second file not found: {path_two}")

    code_one = path_one.read_text(encoding="utf-8")
    code_two = path_two.read_text(encoding="utf-8")

    similarity_ratio = difflib.SequenceMatcher(None, code_one, code_two).ratio()
    similarity_percentage = round(similarity_ratio * 100, 2)
    flagged = similarity_percentage > threshold

    return similarity_percentage, flagged
