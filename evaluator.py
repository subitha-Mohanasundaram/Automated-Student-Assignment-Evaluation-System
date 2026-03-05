"""Core grading script for automated student assignment evaluation."""

from __future__ import annotations

import argparse
import ast
import json
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
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
    plagiarism_detected: bool = False
    plagiarism_matches: list[str] | None = None
    plagiarism_risk_score: float = 0.0
    plagiarism_evidence: list[str] | None = None
    visible_weight: float = 0.6
    hidden_weight: float = 0.4
    visible_score_percent: float = 0.0
    hidden_score_percent: float = 0.0
    weighted_visible_contribution: float = 0.0
    weighted_hidden_contribution: float = 0.0


@dataclass
class ProblemConfig:
    problem_id: str
    default_language: str
    scoring: dict[str, float]
    python_visible_test: str
    python_hidden_test: str
    java_contract: dict[str, str]
    java_visible_cases: list[list[object]]
    java_hidden_cases: list[list[object]]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate a student submission using predefined test packs.")
    parser.add_argument("student_file", help="Path to the student's code file (.py or .java)")
    parser.add_argument("--student-name", dest="student_name", help="Student name (default: inferred username/filename)")
    parser.add_argument("--result-file", default="result.txt", help="Output result file path")
    parser.add_argument("--problem-id", default=None, help="Problem id (default: inferred from path or add_numbers)")
    return parser.parse_args()


def _is_supported_submission(student_file: Path) -> bool:
    return student_file.suffix.lower() in {".py", ".java"}


def _get_repo_root() -> Path:
    return Path(__file__).parent


def _infer_problem_id(student_file: Path) -> str:
    parts = list(student_file.parts)
    if "submissions" in parts:
        idx = parts.index("submissions")
        if idx + 2 < len(parts):
            # submissions/<username>/<problem_id>/file.ext
            possible = parts[idx + 2]
            if "." not in possible:
                return possible
    return "add_numbers"


def _infer_username(student_file: Path) -> str:
    parts = list(student_file.parts)
    if "submissions" in parts:
        idx = parts.index("submissions")
        if idx + 1 < len(parts):
            return parts[idx + 1]
    return student_file.stem


def _load_problem_config(problem_id: str) -> ProblemConfig:
    config_path = _get_repo_root() / "problems" / problem_id / "problem.json"
    if not config_path.exists():
        raise RuntimeError(f"Problem config not found: {config_path}")

    raw = json.loads(config_path.read_text(encoding="utf-8"))
    return ProblemConfig(
        problem_id=raw["problem_id"],
        default_language=raw.get("default_language", "python"),
        scoring=raw.get("scoring", {"visible_weight": 0.6, "hidden_weight": 0.4}),
        python_visible_test=raw["python"]["visible_test"],
        python_hidden_test=raw["python"]["hidden_test"],
        java_contract=raw["java"]["contract"],
        java_visible_cases=raw["java"]["visible_cases"],
        java_hidden_cases=raw["java"]["hidden_cases"],
    )


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


def _weighted_score(
    visible_passed: int,
    visible_total: int,
    hidden_passed: int,
    hidden_total: int,
    scoring: dict[str, float],
) -> tuple[float, float, float, float, float, float, float]:
    visible_weight = float(scoring.get("visible_weight", 0.6))
    hidden_weight = float(scoring.get("hidden_weight", 0.4))
    visible_ratio = (visible_passed / visible_total) if visible_total else 0.0
    hidden_ratio = (hidden_passed / hidden_total) if hidden_total else 0.0
    visible_score_percent = round(visible_ratio * 100, 2)
    hidden_score_percent = round(hidden_ratio * 100, 2)
    weighted_visible_contribution = round(visible_ratio * visible_weight * 100, 2)
    weighted_hidden_contribution = round(hidden_ratio * hidden_weight * 100, 2)
    final_score = round(weighted_visible_contribution + weighted_hidden_contribution, 2)
    return (
        final_score,
        visible_weight,
        hidden_weight,
        visible_score_percent,
        hidden_score_percent,
        weighted_visible_contribution,
        weighted_hidden_contribution,
    )


def _write_result(
    result_file: Path,
    student_name: str,
    problem_id: str,
    language: str,
    summary: TestSummary,
) -> None:
    result_file.parent.mkdir(parents=True, exist_ok=True)
    violations = summary.anti_cheat_violations or []
    anti_cheat_status = "PASS" if summary.anti_cheat_passed else "FAIL"
    plagiarism_status = "DETECTED" if summary.plagiarism_detected else "NOT_DETECTED"
    matches = summary.plagiarism_matches or []
    evidence = summary.plagiarism_evidence or []

    content = (
        f"Student Name: {student_name}\n"
        f"Problem ID: {problem_id}\n"
        f"Language: {language}\n"
        f"Total Test Cases: {summary.total}\n"
        f"Passed Cases: {summary.passed}\n"
        f"Visible Passed: {summary.visible_passed}/{summary.visible_total}\n"
        f"Hidden Passed: {summary.hidden_passed}/{summary.hidden_total}\n"
        f"Visible Weight: {summary.visible_weight}\n"
        f"Hidden Weight: {summary.hidden_weight}\n"
        f"Visible Score Percent: {summary.visible_score_percent}\n"
        f"Hidden Score Percent: {summary.hidden_score_percent}\n"
        f"Weighted Visible Contribution: {summary.weighted_visible_contribution}\n"
        f"Weighted Hidden Contribution: {summary.weighted_hidden_contribution}\n"
        f"Anti-Cheat: {anti_cheat_status}\n"
        f"Plagiarism: {plagiarism_status}\n"
        f"Plagiarism Risk Score: {summary.plagiarism_risk_score}\n"
        f"Score: {summary.score}\n"
    )
    if violations:
        content += "Anti-Cheat Violations:\n"
        for item in violations:
            content += f"- {item}\n"
    if matches:
        content += "Plagiarism Matches:\n"
        for item in matches:
            content += f"- {item}\n"
    if evidence:
        content += "Plagiarism Evidence:\n"
        for item in evidence:
            content += f"- {item}\n"
    result_file.write_text(content, encoding="utf-8")


def _write_result_json(
    result_file: Path,
    student_name: str,
    problem_id: str,
    language: str,
    summary: TestSummary,
) -> Path:
    payload = {
        "student_name": student_name,
        "problem_id": problem_id,
        "language": language,
        "total_test_cases": summary.total,
        "passed_cases": summary.passed,
        "visible": {
            "passed": summary.visible_passed,
            "total": summary.visible_total,
            "weight": summary.visible_weight,
            "score_percent": summary.visible_score_percent,
            "weighted_contribution": summary.weighted_visible_contribution,
        },
        "hidden": {
            "passed": summary.hidden_passed,
            "total": summary.hidden_total,
            "weight": summary.hidden_weight,
            "score_percent": summary.hidden_score_percent,
            "weighted_contribution": summary.weighted_hidden_contribution,
        },
        "anti_cheat": {
            "passed": summary.anti_cheat_passed,
            "violations": summary.anti_cheat_violations or [],
        },
        "plagiarism": {
            "detected": summary.plagiarism_detected,
            "matches": summary.plagiarism_matches or [],
            "risk_score": summary.plagiarism_risk_score,
            "evidence": summary.plagiarism_evidence or [],
        },
        "score": summary.score,
    }
    json_path = result_file.with_suffix(".json")
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return json_path


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

    source = student_file.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(student_file))

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
    source = student_file.read_text(encoding="utf-8")
    violations: list[str] = []
    for pattern in disallowed_patterns:
        if re.search(pattern, source):
            violations.append(f"Disallowed Java usage matched pattern: {pattern}")
    return violations


def _normalize_source_for_fingerprint(source: str, language: str) -> str:
    if language == "python":
        source = re.sub(r"#.*", "", source)
    elif language == "java":
        source = re.sub(r"//.*", "", source)
        source = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    source = re.sub(r"\s+", "", source)
    return source.lower()


def _compute_fingerprint(student_file: Path, language: str) -> str:
    source = student_file.read_text(encoding="utf-8")
    normalized = _normalize_source_for_fingerprint(source, language)
    import hashlib

    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _tokenize_source(source: str, language: str) -> list[str]:
    if language == "python":
        source = re.sub(r"#.*", "", source)
    elif language == "java":
        source = re.sub(r"//.*", "", source)
        source = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    return re.findall(r"[A-Za-z_]\w*|\d+|==|!=|<=|>=|[{}()[\],.;:+\-*/%]", source)


def _jaccard_similarity(tokens_a: list[str], tokens_b: list[str]) -> float:
    set_a = set(tokens_a)
    set_b = set(tokens_b)
    if not set_a and not set_b:
        return 1.0
    union = set_a | set_b
    if not union:
        return 0.0
    return len(set_a & set_b) / len(union)


def _python_structure_signature(source: str) -> list[str]:
    tree = ast.parse(source)
    return [type(node).__name__ for node in ast.walk(tree)]


def _multiset_overlap_similarity(items_a: list[str], items_b: list[str]) -> float:
    from collections import Counter

    counter_a = Counter(items_a)
    counter_b = Counter(items_b)
    if not counter_a and not counter_b:
        return 1.0
    common = sum((counter_a & counter_b).values())
    total = sum((counter_a | counter_b).values())
    if total == 0:
        return 0.0
    return common / total


def _java_structure_signature(source: str) -> list[str]:
    # Lightweight structure proxy for Java when full AST parser is not available.
    signature: list[str] = []
    keywords = [
        "class",
        "public",
        "private",
        "protected",
        "static",
        "if",
        "else",
        "for",
        "while",
        "switch",
        "return",
        "new",
        "try",
        "catch",
    ]
    for kw in keywords:
        signature.extend([kw] * len(re.findall(rf"\b{kw}\b", source)))
    signature.extend(["{"] * source.count("{"))
    signature.extend(["}"] * source.count("}"))
    signature.extend(["("] * source.count("("))
    signature.extend([")"] * source.count(")"))
    return signature


def _compute_similarity_signals(file_a: Path, file_b: Path, language: str) -> tuple[float, float]:
    source_a = file_a.read_text(encoding="utf-8")
    source_b = file_b.read_text(encoding="utf-8")
    tokens_a = _tokenize_source(source_a, language)
    tokens_b = _tokenize_source(source_b, language)
    token_similarity = _jaccard_similarity(tokens_a, tokens_b)

    if language == "python":
        try:
            struct_a = _python_structure_signature(source_a)
            struct_b = _python_structure_signature(source_b)
        except SyntaxError:
            struct_a = tokens_a
            struct_b = tokens_b
    else:
        struct_a = _java_structure_signature(source_a)
        struct_b = _java_structure_signature(source_b)

    structure_similarity = _multiset_overlap_similarity(struct_a, struct_b)
    return token_similarity, structure_similarity


def _detect_plagiarism(
    repo_root: Path,
    student_file: Path,
    language: str,
    problem_id: str,
    current_username: str,
    current_fingerprint: str,
) -> tuple[bool, list[str], float, list[str]]:
    matches: list[str] = []
    evidence: list[str] = []
    max_risk = 0.0
    submissions_dir = repo_root / "submissions"
    if not submissions_dir.exists():
        return False, matches, max_risk, evidence

    token_threshold = 0.88
    structure_threshold = 0.9
    combined_threshold = 0.9

    for file in submissions_dir.rglob(f"*{student_file.suffix.lower()}"):
        if file.resolve() == student_file.resolve():
            continue
        username = _infer_username(file)
        if username == current_username:
            continue

        file_problem_id = _infer_problem_id(file)
        if file_problem_id != problem_id:
            continue

        try:
            other_fp = _compute_fingerprint(file, language)
        except OSError:
            continue
        if other_fp == current_fingerprint:
            matches.append(f"{username}: {file.relative_to(repo_root)} (exact fingerprint match)")
            evidence.append(f"Exact normalized fingerprint match with {username}")
            max_risk = max(max_risk, 100.0)
            continue

        try:
            token_sim, struct_sim = _compute_similarity_signals(student_file, file, language)
        except OSError:
            continue

        combined = (token_sim + struct_sim) / 2.0
        risk = round(
            min(100.0, max(token_sim * 50.0 + struct_sim * 50.0, combined * 100.0)),
            2,
        )
        max_risk = max(max_risk, risk)

        if token_sim >= token_threshold or struct_sim >= structure_threshold or combined >= combined_threshold:
            matches.append(
                f"{username}: {file.relative_to(repo_root)} "
                f"(token={token_sim:.2f}, structure={struct_sim:.2f}, combined={combined:.2f})"
            )
            evidence.append(
                f"High similarity with {username}: token={token_sim:.2f}, structure={struct_sim:.2f}, combined={combined:.2f}"
            )

    detected = len(matches) > 0
    return detected, matches, max_risk, evidence


def _append_attempt_history(
    repo_root: Path,
    *,
    username: str,
    student_name: str,
    problem_id: str,
    language: str,
    submission_file: Path,
    summary: TestSummary,
    fingerprint: str,
) -> None:
    history_path = repo_root / "results" / "attempt_history.jsonl"
    history_path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "username": username,
        "student_name": student_name,
        "problem_id": problem_id,
        "language": language,
        "submission_file": str(submission_file.relative_to(repo_root)),
        "score": summary.score,
        "passed_cases": summary.passed,
        "total_cases": summary.total,
        "anti_cheat_passed": summary.anti_cheat_passed,
        "plagiarism_detected": summary.plagiarism_detected,
        "plagiarism_risk_score": summary.plagiarism_risk_score,
        "fingerprint": fingerprint,
    }
    with history_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")


def _extract_java_public_class_name(source: str) -> str:
    match = re.search(r"\bpublic\s+class\s+([A-Za-z_]\w*)\b", source)
    return match.group(1) if match else "Solution"


def _parse_java_harness_output(output: str) -> tuple[int, int]:
    total_match = re.search(r"TOTAL=(\d+)", output)
    passed_match = re.search(r"PASSED=(\d+)", output)
    if not total_match or not passed_match:
        raise ValueError("Unable to parse Java harness output")
    return int(total_match.group(1)), int(passed_match.group(1))


def _evaluate_java(student_file: Path, config: ProblemConfig) -> TestSummary:
    if shutil.which("javac") is None or shutil.which("java") is None:
        raise RuntimeError("Java runtime tools not found (javac/java).")

    source = student_file.read_text(encoding="utf-8")
    class_name = _extract_java_public_class_name(source)
    expected_method = config.java_contract.get("method_name", "solve")
    expected_static = "true" if config.java_contract.get("static", True) else "false"
    eval_mode = config.java_contract.get("mode", "double_binary")

    visible_cases = config.java_visible_cases
    hidden_cases = config.java_hidden_cases

    if eval_mode == "double_binary":
        harness_source = f"""
public class JavaEvaluatorHarness {{
    private static int runCases(String className, String methodName, boolean mustBeStatic, double[][] cases, double[] expected) throws Exception {{
        Class<?> cls = Class.forName(className);
        java.lang.reflect.Method method = cls.getDeclaredMethod(methodName, double.class, double.class);
        if (mustBeStatic && !java.lang.reflect.Modifier.isStatic(method.getModifiers())) {{
            return 0;
        }}
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
            String methodName = args[1];
            boolean mustBeStatic = Boolean.parseBoolean(args[2]);
            String mode = args[3];
            double[][] cases;
            double[] expected;
            if ("visible".equals(mode)) {{
                cases = new double[][] {{{",".join(f"{{{a},{b}}}" for a, b, _ in visible_cases)}}};
                expected = new double[] {{{",".join(str(c) for _, _, c in visible_cases)}}};
            }} else {{
                cases = new double[][] {{{",".join(f"{{{a},{b}}}" for a, b, _ in hidden_cases)}}};
                expected = new double[] {{{",".join(str(c) for _, _, c in hidden_cases)}}};
            }}
            int passed = runCases(className, methodName, mustBeStatic, cases, expected);
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
        visible_main_args = [class_name, expected_method, expected_static, "visible"]
        hidden_main_args = [class_name, expected_method, expected_static, "hidden"]
    elif eval_mode == "string_unary":
        # Expected method contract: public static String <method>(String input)
        visible_cases_lit = ",".join(json.dumps(str(item[0])) for item in visible_cases)
        visible_expected_lit = ",".join(json.dumps(str(item[1])) for item in visible_cases)
        hidden_cases_lit = ",".join(json.dumps(str(item[0])) for item in hidden_cases)
        hidden_expected_lit = ",".join(json.dumps(str(item[1])) for item in hidden_cases)
        harness_source = f"""
public class JavaEvaluatorHarness {{
    private static int runCases(String className, String methodName, boolean mustBeStatic, String[] cases, String[] expected) throws Exception {{
        Class<?> cls = Class.forName(className);
        java.lang.reflect.Method method = cls.getDeclaredMethod(methodName, String.class);
        if (mustBeStatic && !java.lang.reflect.Modifier.isStatic(method.getModifiers())) {{
            return 0;
        }}
        int passed = 0;
        for (int i = 0; i < cases.length; i++) {{
            Object raw = method.invoke(null, cases[i]);
            String actual = raw == null ? "" : raw.toString();
            if (actual.trim().equals(expected[i].trim())) {{
                passed++;
            }}
        }}
        return passed;
    }}

    public static void main(String[] args) {{
        try {{
            String className = args[0];
            String methodName = args[1];
            boolean mustBeStatic = Boolean.parseBoolean(args[2]);
            String mode = args[3];
            String[] cases;
            String[] expected;
            if ("visible".equals(mode)) {{
                cases = new String[] {{{visible_cases_lit}}};
                expected = new String[] {{{visible_expected_lit}}};
            }} else {{
                cases = new String[] {{{hidden_cases_lit}}};
                expected = new String[] {{{hidden_expected_lit}}};
            }}
            int passed = runCases(className, methodName, mustBeStatic, cases, expected);
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
        visible_main_args = [class_name, expected_method, expected_static, "visible"]
        hidden_main_args = [class_name, expected_method, expected_static, "hidden"]
    else:
        raise RuntimeError(f"Unsupported Java evaluation mode: {eval_mode}")

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
            ["java", "-cp", str(temp_path), "JavaEvaluatorHarness", *visible_main_args],
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
            cwd=str(temp_path),
        )
        hidden_proc = subprocess.run(
            ["java", "-cp", str(temp_path), "JavaEvaluatorHarness", *hidden_main_args],
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
    (
        score,
        visible_weight,
        hidden_weight,
        visible_score_percent,
        hidden_score_percent,
        weighted_visible_contribution,
        weighted_hidden_contribution,
    ) = _weighted_score(visible_passed, visible_total, hidden_passed, hidden_total, config.scoring)
    return TestSummary(
        total=total,
        passed=passed,
        score=score,
        visible_total=visible_total,
        visible_passed=visible_passed,
        hidden_total=hidden_total,
        hidden_passed=hidden_passed,
        visible_weight=visible_weight,
        hidden_weight=hidden_weight,
        visible_score_percent=visible_score_percent,
        hidden_score_percent=hidden_score_percent,
        weighted_visible_contribution=weighted_visible_contribution,
        weighted_hidden_contribution=weighted_hidden_contribution,
    )


def _evaluate_python(student_file: Path, config: ProblemConfig) -> TestSummary:
    repo_root = _get_repo_root()
    visible_test_file = repo_root / config.python_visible_test
    hidden_test_file = repo_root / config.python_hidden_test
    if not visible_test_file.exists():
        raise RuntimeError(f"Visible test file not found: {visible_test_file}")
    if not hidden_test_file.exists():
        raise RuntimeError(f"Hidden test file not found: {hidden_test_file}")

    with tempfile.TemporaryDirectory(prefix="grader_") as temp_dir:
        visible_xml_path = Path(temp_dir) / "visible_result.xml"
        hidden_xml_path = Path(temp_dir) / "hidden_result.xml"

        visible_process = _run_pytest(student_file, visible_test_file, visible_xml_path)
        hidden_process = _run_pytest(student_file, hidden_test_file, hidden_xml_path)

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
    (
        score,
        visible_weight,
        hidden_weight,
        visible_score_percent,
        hidden_score_percent,
        weighted_visible_contribution,
        weighted_hidden_contribution,
    ) = _weighted_score(
        visible_summary.passed,
        visible_summary.total,
        hidden_summary.passed,
        hidden_summary.total,
        config.scoring,
    )
    return TestSummary(
        total=combined_total,
        passed=combined_passed,
        score=score,
        visible_total=visible_summary.total,
        visible_passed=visible_summary.passed,
        hidden_total=hidden_summary.total,
        hidden_passed=hidden_summary.passed,
        visible_weight=visible_weight,
        hidden_weight=hidden_weight,
        visible_score_percent=visible_score_percent,
        hidden_score_percent=hidden_score_percent,
        weighted_visible_contribution=weighted_visible_contribution,
        weighted_hidden_contribution=weighted_hidden_contribution,
    )


def evaluate_student(
    student_file: Path,
    student_name: str,
    result_file: Path,
    problem_id: str,
) -> int:
    repo_root = _get_repo_root()
    language = "python" if student_file.suffix.lower() == ".py" else "java"
    username = _infer_username(student_file)

    try:
        config = _load_problem_config(problem_id)
    except RuntimeError as exc:
        print(f"Error: {exc}")
        return 1

    try:
        if language == "python":
            violations = _run_python_anti_cheat(student_file)
        else:
            violations = _run_java_anti_cheat(student_file)
    except (OSError, SyntaxError) as exc:
        print(f"Error: anti-cheat failed: {exc}")
        return 1

    fingerprint = _compute_fingerprint(student_file, language)
    plagiarism_detected, plagiarism_matches, plagiarism_risk_score, plagiarism_evidence = _detect_plagiarism(
        repo_root=repo_root,
        student_file=student_file,
        language=language,
        problem_id=problem_id,
        current_username=username,
        current_fingerprint=fingerprint,
    )

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
            plagiarism_detected=plagiarism_detected,
            plagiarism_matches=plagiarism_matches,
            plagiarism_risk_score=plagiarism_risk_score,
            plagiarism_evidence=plagiarism_evidence,
        )
        _write_result(result_file=result_file, student_name=student_name, problem_id=problem_id, language=language, summary=summary)
        _write_result_json(result_file=result_file, student_name=student_name, problem_id=problem_id, language=language, summary=summary)
        _append_attempt_history(
            repo_root,
            username=username,
            student_name=student_name,
            problem_id=problem_id,
            language=language,
            submission_file=student_file,
            summary=summary,
            fingerprint=fingerprint,
        )
        print("Anti-cheat checks failed. Submission disqualified.")
        print(f"Result saved to: {result_file}")
        return 0

    try:
        if language == "python":
            summary = _evaluate_python(student_file, config)
        else:
            summary = _evaluate_java(student_file, config)
    except (RuntimeError, ET.ParseError, ValueError, subprocess.TimeoutExpired) as exc:
        print(f"Error: {exc}")
        return 1

    summary.anti_cheat_passed = True
    summary.anti_cheat_violations = []
    summary.plagiarism_detected = plagiarism_detected
    summary.plagiarism_matches = plagiarism_matches
    summary.plagiarism_risk_score = plagiarism_risk_score
    summary.plagiarism_evidence = plagiarism_evidence
    if plagiarism_detected:
        summary.score = max(round(summary.score * 0.7, 2), 0.0)

    _write_result(result_file=result_file, student_name=student_name, problem_id=problem_id, language=language, summary=summary)
    json_path = _write_result_json(result_file=result_file, student_name=student_name, problem_id=problem_id, language=language, summary=summary)
    _append_attempt_history(
        repo_root,
        username=username,
        student_name=student_name,
        problem_id=problem_id,
        language=language,
        submission_file=student_file,
        summary=summary,
        fingerprint=fingerprint,
    )
    print(f"Result saved to: {result_file}")
    print(f"Result JSON saved to: {json_path}")
    return 0


def main() -> int:
    args = parse_args()

    student_file = Path(args.student_file).resolve()
    if not student_file.exists() or not _is_supported_submission(student_file):
        print("Error: student_file must be an existing .py or .java file")
        return 1

    student_name = args.student_name.strip() if args.student_name else _infer_username(student_file)
    result_file = Path(args.result_file).resolve()
    problem_id = args.problem_id.strip() if args.problem_id else _infer_problem_id(student_file)

    return evaluate_student(student_file=student_file, student_name=student_name, result_file=result_file, problem_id=problem_id)


if __name__ == "__main__":
    raise SystemExit(main())
