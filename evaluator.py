"""Core grading script for automated student assignment evaluation."""

from __future__ import annotations

import argparse
import ast
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
    visible_total: int = 0
    visible_passed: int = 0
    hidden_total: int = 0
    hidden_passed: int = 0
    anti_cheat_passed: bool = True
    anti_cheat_violations: list[str] | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate a student Python submission using pytest.")
    parser.add_argument("student_file", help="Path to the student's Python file")
    parser.add_argument("--student-name", dest="student_name", help="Student name (default: filename)")
    parser.add_argument("--result-file", default="result.txt", help="Output result file path")
    return parser.parse_args()


def _get_test_files() -> tuple[Path, Path]:
    tests_dir = Path(__file__).parent / "tests"
    visible = tests_dir / "test_student_submission.py"
    hidden = tests_dir / "test_student_submission_hidden.py"
    return visible, hidden


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
    violations = summary.anti_cheat_violations or []
    anti_cheat_status = "PASS" if summary.anti_cheat_passed else "FAIL"
    content = (
        f"Student Name: {student_name}\n"
        f"Total Test Cases: {summary.total}\n"
        f"Passed Cases: {summary.passed}\n"
        f"Visible Passed: {summary.visible_passed}/{summary.visible_total}\n"
        f"Hidden Passed: {summary.hidden_passed}/{summary.hidden_total}\n"
        f"Anti-Cheat: {anti_cheat_status}\n"
        f"Score: {summary.score}\n"
    )
    if violations:
        content += "Anti-Cheat Violations:\n"
        for item in violations:
            content += f"- {item}\n"
    result_file.write_text(content, encoding="utf-8")


def _run_pytest(student_file: Path, test_file: Path, junit_xml_path: Path) -> subprocess.CompletedProcess[str]:
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
    return subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=20)


def _run_anti_cheat(student_file: Path) -> list[str]:
    disallowed_import_roots = {"os", "subprocess", "socket", "requests", "http", "urllib"}
    disallowed_calls = {"eval", "exec", "compile", "__import__"}
    violations: list[str] = []

    try:
        source = student_file.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"Unable to read student file: {exc}"]

    try:
        tree = ast.parse(source, filename=str(student_file))
    except SyntaxError as exc:
        return [f"Syntax error in submission: {exc}"]

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in disallowed_import_roots:
                    violations.append(f"Disallowed import: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                root = node.module.split(".")[0]
                if root in disallowed_import_roots:
                    violations.append(f"Disallowed import-from: {node.module}")
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in disallowed_calls:
                violations.append(f"Disallowed function call: {node.func.id}(...)")

    # Keep messages unique while preserving order.
    seen: set[str] = set()
    unique_violations: list[str] = []
    for item in violations:
        if item not in seen:
            seen.add(item)
            unique_violations.append(item)
    return unique_violations


def evaluate_student(student_file: Path, student_name: str, result_file: Path) -> int:
    violations = _run_anti_cheat(student_file)
    if violations:
        summary = TestSummary(
            total=0,
            passed=0,
            score=0.0,
            visible_total=0,
            visible_passed=0,
            hidden_total=0,
            hidden_passed=0,
            anti_cheat_passed=False,
            anti_cheat_violations=violations,
        )
        _write_result(result_file=result_file, student_name=student_name, summary=summary)
        print("Anti-cheat checks failed. Submission disqualified.")
        print(f"Result saved to: {result_file}")
        return 0

    visible_test_file, hidden_test_file = _get_test_files()
    if not visible_test_file.exists():
        print(f"Error: Visible test file not found: {visible_test_file}")
        return 1
    if not hidden_test_file.exists():
        print(f"Error: Hidden test file not found: {hidden_test_file}")
        return 1

    with tempfile.TemporaryDirectory(prefix="grader_") as temp_dir:
        visible_xml_path = Path(temp_dir) / "visible_result.xml"
        hidden_xml_path = Path(temp_dir) / "hidden_result.xml"

        try:
            visible_process = _run_pytest(student_file, visible_test_file, visible_xml_path)
            hidden_process = _run_pytest(student_file, hidden_test_file, hidden_xml_path)
        except subprocess.TimeoutExpired:
            print("Error: Test execution timed out.")
            return 1
        except OSError as exc:
            print(f"Error: Failed to execute pytest: {exc}")
            return 1

        if visible_process.stdout:
            print(visible_process.stdout.strip())
        if visible_process.stderr:
            print(visible_process.stderr.strip())
        if hidden_process.stdout:
            print(hidden_process.stdout.strip())
        if hidden_process.stderr:
            print(hidden_process.stderr.strip())

        if not visible_xml_path.exists() or not hidden_xml_path.exists():
            print("Error: pytest did not generate expected JUnit XML output.")
            return 1

        try:
            visible_summary = _parse_junit_xml(visible_xml_path)
            hidden_summary = _parse_junit_xml(hidden_xml_path)
        except (ET.ParseError, ValueError) as exc:
            print(f"Error: Unable to parse pytest results: {exc}")
            return 1

    combined_total = visible_summary.total + hidden_summary.total
    combined_passed = visible_summary.passed + hidden_summary.passed
    combined_score = round((combined_passed / combined_total) * 100, 2) if combined_total > 0 else 0.0
    summary = TestSummary(
        total=combined_total,
        passed=combined_passed,
        score=combined_score,
        visible_total=visible_summary.total,
        visible_passed=visible_summary.passed,
        hidden_total=hidden_summary.total,
        hidden_passed=hidden_summary.passed,
        anti_cheat_passed=True,
        anti_cheat_violations=[],
    )

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
