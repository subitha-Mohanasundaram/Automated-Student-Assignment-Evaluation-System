"""Core grading script for automated student assignment evaluation."""

from __future__ import annotations

import argparse
import ast
import re
import shutil
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


def _is_supported_submission(student_file: Path) -> bool:
    return student_file.suffix.lower() in {".py", ".java"}


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


def _run_python_anti_cheat(student_file: Path) -> list[str]:
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


def _run_java_anti_cheat(student_file: Path) -> list[str]:
    disallowed_patterns = [
        r"\bProcessBuilder\b",
        r"\bRuntime\s*\.\s*getRuntime\s*\(",
        r"\bSystem\s*\.\s*exit\s*\(",
        r"\bjava\.net\b",
        r"\bjava\.nio\.file\b",
    ]
    try:
        source = student_file.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"Unable to read student file: {exc}"]

    violations: list[str] = []
    for pattern in disallowed_patterns:
        if re.search(pattern, source):
            violations.append(f"Disallowed Java usage matched pattern: {pattern}")
    return violations


def _extract_java_public_class_name(source: str) -> str:
    match = re.search(r"\bpublic\s+class\s+([A-Za-z_]\w*)\b", source)
    return match.group(1) if match else "Solution"


def _parse_java_harness_output(output: str) -> tuple[int, int]:
    total_match = re.search(r"TOTAL=(\d+)", output)
    passed_match = re.search(r"PASSED=(\d+)", output)
    if not total_match or not passed_match:
        raise ValueError("Unable to parse Java harness output")
    return int(total_match.group(1)), int(passed_match.group(1))


def _evaluate_java(student_file: Path) -> TestSummary:
    if shutil.which("javac") is None or shutil.which("java") is None:
        raise RuntimeError("Java runtime tools not found (javac/java).")

    # Visible and hidden test data for Java submissions. Expected method:
    # public static double addNumbers(double a, double b)
    visible_cases = [(2.0, 3.0, 5.0), (-2.0, -7.0, -9.0), (-2.0, 10.0, 8.0), (0.0, 99.0, 99.0)]
    hidden_cases = [(10_000_000.0, 23_000_000.0, 33_000_000.0), (0.1, 0.2, 0.3), (-2.5, 1.5, -1.0)]

    source = student_file.read_text(encoding="utf-8")
    class_name = _extract_java_public_class_name(source)

    harness_source = f"""
public class JavaEvaluatorHarness {{
    private static int runCases(String className, double[][] cases, double[] expected) throws Exception {{
        Class<?> cls = Class.forName(className);
        java.lang.reflect.Method method = cls.getDeclaredMethod("addNumbers", double.class, double.class);
        int passed = 0;
        for (int i = 0; i < cases.length; i++) {{
            Object raw = method.invoke(null, cases[i][0], cases[i][1]);
            if (!(raw instanceof Number)) {{
                continue;
            }}
            double actual = ((Number) raw).doubleValue();
            if (Math.abs(actual - expected[i]) < 1e-9) {{
                passed++;
            }}
        }}
        return passed;
    }}

    public static void main(String[] args) {{
        try {{
            String className = args[0];
            String mode = args[1];
            double[][] cases;
            double[] expected;
            if ("visible".equals(mode)) {{
                cases = new double[][] {{{",".join(f"{{{a},{b}}}" for a, b, _ in visible_cases)}}};
                expected = new double[] {{{",".join(str(c) for _, _, c in visible_cases)}}};
            }} else {{
                cases = new double[][] {{{",".join(f"{{{a},{b}}}" for a, b, _ in hidden_cases)}}};
                expected = new double[] {{{",".join(str(c) for _, _, c in hidden_cases)}}};
            }}
            int passed = runCases(className, cases, expected);
            System.out.println("TOTAL=" + cases.length);
            System.out.println("PASSED=" + passed);
        }} catch (Throwable t) {{
            t.printStackTrace();
            System.out.println("TOTAL=0");
            System.out.println("PASSED=0");
        }}
    }}
}}
"""

    with tempfile.TemporaryDirectory(prefix="java_grader_") as temp_dir:
        temp_path = Path(temp_dir)
        student_java_path = temp_path / f"{class_name}.java"
        harness_java_path = temp_path / "JavaEvaluatorHarness.java"
        student_java_path.write_text(source, encoding="utf-8")
        harness_java_path.write_text(harness_source, encoding="utf-8")

        compile_proc = subprocess.run(
            ["javac", str(student_java_path), str(harness_java_path)],
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
            cwd=str(temp_path),
        )
        if compile_proc.stdout:
            print(compile_proc.stdout.strip())
        if compile_proc.stderr:
            print(compile_proc.stderr.strip())
        if compile_proc.returncode != 0:
            return TestSummary(total=7, passed=0, score=0.0, visible_total=4, visible_passed=0, hidden_total=3, hidden_passed=0)

        visible_proc = subprocess.run(
            ["java", "-cp", str(temp_path), "JavaEvaluatorHarness", class_name, "visible"],
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
            cwd=str(temp_path),
        )
        hidden_proc = subprocess.run(
            ["java", "-cp", str(temp_path), "JavaEvaluatorHarness", class_name, "hidden"],
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
            cwd=str(temp_path),
        )

        if visible_proc.stdout:
            print(visible_proc.stdout.strip())
        if visible_proc.stderr:
            print(visible_proc.stderr.strip())
        if hidden_proc.stdout:
            print(hidden_proc.stdout.strip())
        if hidden_proc.stderr:
            print(hidden_proc.stderr.strip())

        visible_total, visible_passed = _parse_java_harness_output(visible_proc.stdout)
        hidden_total, hidden_passed = _parse_java_harness_output(hidden_proc.stdout)

    total = visible_total + hidden_total
    passed = visible_passed + hidden_passed
    score = round((passed / total) * 100, 2) if total else 0.0
    return TestSummary(
        total=total,
        passed=passed,
        score=score,
        visible_total=visible_total,
        visible_passed=visible_passed,
        hidden_total=hidden_total,
        hidden_passed=hidden_passed,
    )


def _evaluate_python(student_file: Path) -> TestSummary:
    visible_test_file, hidden_test_file = _get_test_files()
    if not visible_test_file.exists():
        raise RuntimeError(f"Visible test file not found: {visible_test_file}")
    if not hidden_test_file.exists():
        raise RuntimeError(f"Hidden test file not found: {hidden_test_file}")

    with tempfile.TemporaryDirectory(prefix="grader_") as temp_dir:
        visible_xml_path = Path(temp_dir) / "visible_result.xml"
        hidden_xml_path = Path(temp_dir) / "hidden_result.xml"

        try:
            visible_process = _run_pytest(student_file, visible_test_file, visible_xml_path)
            hidden_process = _run_pytest(student_file, hidden_test_file, hidden_xml_path)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("Test execution timed out.") from exc
        except OSError as exc:
            raise RuntimeError(f"Failed to execute pytest: {exc}") from exc

        if visible_process.stdout:
            print(visible_process.stdout.strip())
        if visible_process.stderr:
            print(visible_process.stderr.strip())
        if hidden_process.stdout:
            print(hidden_process.stdout.strip())
        if hidden_process.stderr:
            print(hidden_process.stderr.strip())

        if not visible_xml_path.exists() or not hidden_xml_path.exists():
            raise RuntimeError("pytest did not generate expected JUnit XML output.")

        visible_summary = _parse_junit_xml(visible_xml_path)
        hidden_summary = _parse_junit_xml(hidden_xml_path)

    combined_total = visible_summary.total + hidden_summary.total
    combined_passed = visible_summary.passed + hidden_summary.passed
    combined_score = round((combined_passed / combined_total) * 100, 2) if combined_total > 0 else 0.0
    return TestSummary(
        total=combined_total,
        passed=combined_passed,
        score=combined_score,
        visible_total=visible_summary.total,
        visible_passed=visible_summary.passed,
        hidden_total=hidden_summary.total,
        hidden_passed=hidden_summary.passed,
    )


def evaluate_student(student_file: Path, student_name: str, result_file: Path) -> int:
    if student_file.suffix.lower() == ".py":
        violations = _run_python_anti_cheat(student_file)
    elif student_file.suffix.lower() == ".java":
        violations = _run_java_anti_cheat(student_file)
    else:
        print("Error: unsupported submission format")
        return 1

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

    try:
        if student_file.suffix.lower() == ".py":
            summary = _evaluate_python(student_file)
        else:
            summary = _evaluate_java(student_file)
    except (RuntimeError, ET.ParseError, ValueError, subprocess.TimeoutExpired) as exc:
        print(f"Error: {exc}")
        return 1

    summary.anti_cheat_passed = True
    summary.anti_cheat_violations = []

    _write_result(result_file=result_file, student_name=student_name, summary=summary)
    print(f"Result saved to: {result_file}")
    return 0


def main() -> int:
    args = parse_args()

    student_file = Path(args.student_file).resolve()
    if not student_file.exists() or not _is_supported_submission(student_file):
        print("Error: student_file must be an existing .py or .java file")
        return 1

    student_name = args.student_name.strip() if args.student_name else student_file.stem
    result_file = Path(args.result_file).resolve()

    return evaluate_student(student_file=student_file, student_name=student_name, result_file=result_file)


if __name__ == "__main__":
    raise SystemExit(main())
