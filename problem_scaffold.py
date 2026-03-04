"""Scaffold a new configurable problem pack for the evaluator."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a new problem config + test templates.")
    parser.add_argument("problem_id", help="Problem id, e.g. swap_numbers")
    parser.add_argument("--python-function", default="solve", help="Expected Python function name")
    parser.add_argument("--java-method", default="solve", help="Expected Java static method name")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing problem files if they already exist",
    )
    return parser.parse_args()


def _safe_problem_id(problem_id: str) -> str:
    normalized = problem_id.strip().lower().replace("-", "_")
    if not re.fullmatch(r"[a-z0-9_]+", normalized):
        raise ValueError("problem_id must contain only letters, numbers, '_' or '-'")
    return normalized


def _write_text(path: Path, content: str, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"File already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).parent
    problem_id = _safe_problem_id(args.problem_id)

    problems_dir = repo_root / "problems" / problem_id
    tests_dir = repo_root / "tests" / "problems" / problem_id
    visible_test_path = tests_dir / "test_visible.py"
    hidden_test_path = tests_dir / "test_hidden.py"
    config_path = problems_dir / "problem.json"

    python_function = args.python_function.strip()
    java_method = args.java_method.strip()

    config = {
        "problem_id": problem_id,
        "default_language": "python",
        "scoring": {"visible_weight": 0.6, "hidden_weight": 0.4},
        "python": {
            "visible_test": str(visible_test_path.relative_to(repo_root)).replace("\\", "/"),
            "hidden_test": str(hidden_test_path.relative_to(repo_root)).replace("\\", "/"),
        },
        "java": {
            "contract": {"class_name_hint": "student_solution", "method_name": java_method, "static": True},
            "visible_cases": [[1.0, 2.0, 3.0], [5.0, 5.0, 10.0]],
            "hidden_cases": [[10.0, -4.0, 6.0], [0.5, 0.5, 1.0]],
        },
    }

    visible_test = f'''"""Visible tests for problem: {problem_id}."""

from __future__ import annotations

import pytest


def _get_target(student_module):
    if not hasattr(student_module, "{python_function}"):
        pytest.fail("Student file must define function: {python_function}(a, b)")
    return getattr(student_module, "{python_function}")


def test_visible_case_1(student_module) -> None:
    fn = _get_target(student_module)
    assert fn(1, 2) == 3


def test_visible_case_2(student_module) -> None:
    fn = _get_target(student_module)
    assert fn(4, 5) == 9
'''

    hidden_test = f'''"""Hidden tests for problem: {problem_id}."""

from __future__ import annotations

import pytest


def _get_target(student_module):
    if not hasattr(student_module, "{python_function}"):
        pytest.fail("Student file must define function: {python_function}(a, b)")
    return getattr(student_module, "{python_function}")


def test_hidden_case_1(student_module) -> None:
    fn = _get_target(student_module)
    assert fn(-3, 7) == 4


def test_hidden_case_2(student_module) -> None:
    fn = _get_target(student_module)
    assert fn(0, 0) == 0
'''

    try:
        _write_text(config_path, json.dumps(config, indent=2) + "\n", args.force)
        _write_text(visible_test_path, visible_test, args.force)
        _write_text(hidden_test_path, hidden_test, args.force)
    except (FileExistsError, OSError, ValueError) as exc:
        print(f"Error: {exc}")
        return 1

    print(f"Scaffold created for problem '{problem_id}'.")
    print(f"- Config: {config_path}")
    print(f"- Visible tests: {visible_test_path}")
    print(f"- Hidden tests: {hidden_test_path}")
    print("Next: edit generated tests/config to match your real problem statement and rubric.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
