"""Core grading script for automated student assignment evaluation."""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path


@dataclass
class TestSummary:
    total: int
    passed: int
    score: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate a student Python submission using pytest.")
    parser.add_argument("student_file", help="Path to the student's Python file")
    parser.add_argument("--student-name", dest="student_name", help="Student name (default: filename)")
    parser.add_argument("--result-file", default="result.txt", help="Output result file path")
    return parser.parse_args()


def _get_test_file() -> Path:
    return Path(__file__).parent / "tests" / "test_student_submission.py"


def _parse_junit_xml(junit_xml_path: Path) -> TestSummary:
    tree = ET.parse(junit_xml_path)
    root = tree.getroot()

    if root.tag == "testsuite":
        suite = root
    elif root.tag == "testsuites":
        suite = root.find("testsuite")
    else:
        suite = None

    if suite is None:
        raise ValueError("Unable to parse pytest JUnit XML output")

    total = int(suite.attrib.get("tests", 0))
    failures = int(suite.attrib.get("failures", 0))
    errors = int(suite.attrib.get("errors", 0))
    skipped = int(suite.attrib.get("skipped", 0))
    passed = max(total - failures - errors - skipped, 0)
    score = round((passed / total) * 100, 2) if total > 0 else 0.0

    return TestSummary(total=total, passed=passed, score=score)


def _write_result(result_file: Path, student_name: str, summary: TestSummary) -> None:
    result_file.parent.mkdir(parents=True, exist_ok=True)
    content = (
        f"Student Name: {student_name}\n"
        f"Total Test Cases: {summary.total}\n"
        f"Passed Cases: {summary.passed}\n"
        f"Score: {summary.score}\n"
    )
    result_file.write_text(content, encoding="utf-8")


def evaluate_student(student_file: Path, student_name: str, result_file: Path) -> int:
    test_file = _get_test_file()
    if not test_file.exists():
        print(f"Error: Predefined test file not found: {test_file}")
        return 1

    with tempfile.TemporaryDirectory(prefix="grader_") as temp_dir:
        junit_xml_path = Path(temp_dir) / "pytest_result.xml"
        cmd = [
            sys.executable,
            "-m",
            "pytest",
            str(test_file),
            "--student-file",
            str(student_file),
            "--junitxml",
            str(junit_xml_path),
            "-q",
        ]

        try:
            process = subprocess.run(cmd, capture_output=True, text=True, check=False)
        except OSError as exc:
            print(f"Error: Failed to execute pytest: {exc}")
            return 1

        if process.stdout:
            print(process.stdout.strip())
        if process.stderr:
            print(process.stderr.strip())

        if not junit_xml_path.exists():
            print("Error: pytest did not generate JUnit XML output.")
            return 1

        try:
            summary = _parse_junit_xml(junit_xml_path)
        except (ET.ParseError, ValueError) as exc:
            print(f"Error: Unable to parse pytest results: {exc}")
            return 1

    _write_result(result_file=result_file, student_name=student_name, summary=summary)
    print(f"Result saved to: {result_file}")
    return 0


def main() -> int:
    args = parse_args()

    student_file = Path(args.student_file).resolve()
    if not student_file.exists() or student_file.suffix != ".py":
        print("Error: student_file must be an existing .py file")
        return 1

    student_name = args.student_name.strip() if args.student_name else student_file.stem
    result_file = Path(args.result_file).resolve()

    return evaluate_student(student_file=student_file, student_name=student_name, result_file=result_file)


if __name__ == "__main__":
    raise SystemExit(main())
