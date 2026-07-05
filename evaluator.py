"""Core grading script for automated student assignment evaluation."""

from __future__ import annotations

import argparse
import ast
import os
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
from typing import Any


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
    case_results: list[dict[str, object]] | None = None
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
    anti_cheat: dict[str, object]


@dataclass
class IOCaseResult:
    visibility: str
    input: str
    expected: str
    actual: str
    passed: bool
    weight: float = 1.0
    error: str | None = None


def _normalize_output(text: str) -> str:
    # Normalize common platform differences and trailing whitespace.
    return (text or "").replace("\r\n", "\n").strip()


def _detect_language_from_path(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".py":
        return "python"
    if ext == ".java":
        return "java"
    if ext == ".js":
        return "javascript"
    if ext == ".c":
        return "c"
    return "cpp"


def _compile_and_prepare_io(*, language: str, student_file: Path, temp_dir: Path) -> tuple[list[str], Path | None]:
    """Returns (run_cmd, working_dir) where run_cmd is executed with stdin per case.

    For compiled languages, compiles to temp_dir and returns executable run cmd.
    """
    lang = language.lower().strip()
    if lang == "python":
        submission = temp_dir / "submission.py"
        submission.write_text(student_file.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff"), encoding="utf-8")
        return ["python", str(submission.name)], temp_dir
    if lang == "javascript":
        submission = temp_dir / "submission.js"
        submission.write_text(student_file.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff"), encoding="utf-8")
        return ["node", str(submission.name)], temp_dir
    if lang == "java":
        if shutil.which("javac") is None or shutil.which("java") is None:
            raise RuntimeError("Java runtime tools not found (javac/java).")
        source = student_file.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")
        class_name = _extract_java_public_class_name(source)
        submission = temp_dir / f"{class_name}.java"
        submission.write_text(source, encoding="utf-8")
        cp = subprocess.run(["javac", submission.name], cwd=temp_dir, capture_output=True, text=True, check=False, timeout=60)
        if cp.returncode != 0:
            raise RuntimeError(f"Java compile failed: {cp.stderr or cp.stdout}")
        return ["java", "-cp", str(temp_dir), class_name], temp_dir
    if lang == "c":
        if shutil.which("gcc") is None:
            raise RuntimeError("C compiler not found (gcc).")
        submission = temp_dir / "submission.c"
        submission.write_text(student_file.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff"), encoding="utf-8")
        exe = temp_dir / "a.out"
        cp = subprocess.run(
            ["gcc", "-O2", "-std=c11", submission.name, "-o", str(exe.name)],
            cwd=temp_dir,
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        if cp.returncode != 0:
            raise RuntimeError(f"C compile failed: {cp.stderr or cp.stdout}")
        return [str(exe)], temp_dir
    # cpp
    if shutil.which("g++") is None:
        raise RuntimeError("C++ compiler not found (g++).")
    submission = temp_dir / "submission.cpp"
    submission.write_text(student_file.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff"), encoding="utf-8")
    exe = temp_dir / "a.out"
    cp = subprocess.run(
        ["g++", "-std=c++17", "-O2", submission.name, "-o", str(exe.name)],
        cwd=temp_dir,
        capture_output=True,
        text=True,
        check=False,
        timeout=90,
    )
    if cp.returncode != 0:
        raise RuntimeError(f"C++ compile failed: {cp.stderr or cp.stdout}")
    return [str(exe)], temp_dir


def _evaluate_io_cases(*, language: str, student_file: Path, cases: list[Any]) -> TestSummary:
    """Evaluate stdin->stdout test cases (coding interview style).

    cases must be a list of assignment_intel.testcases.IOTestCase objects.
    """
    # Import lazily to avoid evaluator being used standalone without the platform package.
    from assignment_intel.testcases import IOTestCase  # type: ignore

    typed_cases: list[IOTestCase] = [c for c in cases if isinstance(c, IOTestCase)]
    if not typed_cases:
        raise RuntimeError("No IO test cases provided.")

    temp_dir = Path(tempfile.mkdtemp(prefix="io_eval_"))
    per_case: list[IOCaseResult] = []
    try:
        run_cmd, cwd = _compile_and_prepare_io(language=language, student_file=student_file, temp_dir=temp_dir)

        # Suite scoring with required weights: visible 30%, hidden 50%, stress 20%.
        visible_total = 0
        visible_passed = 0
        hidden_total = 0
        hidden_passed = 0
        stress_total = 0
        stress_passed = 0

        for c in typed_cases:
            vis = str(c.visibility or "visible").strip().lower()
            if vis not in {"visible", "hidden", "stress"}:
                vis = "visible"
            if vis == "visible":
                visible_total += 1
            elif vis == "hidden":
                hidden_total += 1
            else:
                stress_total += 1

            try:
                cp = subprocess.run(
                    run_cmd,
                    cwd=cwd,
                    input=c.input_text,
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=5,
                )
                actual = _normalize_output(cp.stdout or "")
                expected = _normalize_output(c.expected_output)
                ok = (cp.returncode == 0) and (actual == expected)
                if ok:
                    if vis == "visible":
                        visible_passed += 1
                    elif vis == "hidden":
                        hidden_passed += 1
                    else:
                        stress_passed += 1
                per_case.append(
                    IOCaseResult(
                        visibility=vis,
                        # Never reveal hidden/stress inputs/expected in student-facing reports.
                        input=c.input_text if vis == "visible" else "",
                        expected=c.expected_output if vis == "visible" else "",
                        actual=(cp.stdout or "") if vis == "visible" else "",
                        passed=ok,
                        weight=float(c.weight),
                        error=None if ok else (cp.stderr or "").strip() or (f"exit_code={cp.returncode}" if cp.returncode != 0 else "wrong_answer"),
                    )
                )
            except subprocess.TimeoutExpired:
                per_case.append(
                    IOCaseResult(
                        visibility=vis,
                        input=c.input_text,
                        expected=c.expected_output,
                        actual="",
                        passed=False,
                        weight=float(c.weight),
                        error="timeout",
                    )
                )

        total = len(typed_cases)
        passed = visible_passed + hidden_passed + stress_passed
        visible_score_percent = round((visible_passed / visible_total) * 100.0, 2) if visible_total else 0.0
        hidden_score_percent = round((hidden_passed / hidden_total) * 100.0, 2) if hidden_total else 0.0
        stress_score_percent = round((stress_passed / stress_total) * 100.0, 2) if stress_total else 0.0
        visible_weight = 0.3
        hidden_weight = 0.5
        stress_weight = 0.2
        weighted_visible_contribution = round(visible_score_percent * visible_weight, 2)
        weighted_hidden_contribution = round(hidden_score_percent * hidden_weight, 2)
        weighted_stress_contribution = round(stress_score_percent * stress_weight, 2)
        score_percent = round(weighted_visible_contribution + weighted_hidden_contribution + weighted_stress_contribution, 2)

        # Store per-case results in the evidence fields so it appears in JSON output under plagiarism_evidence for now.
        # (Keeps backwards compatibility with the current JSON schema writer.)
        return TestSummary(
            total=total,
            passed=passed,
            score=score_percent,
            visible_total=visible_total,
            visible_passed=visible_passed,
            hidden_total=hidden_total,
            hidden_passed=hidden_passed,
            # overload hidden_* fields are already in the schema; stress is added via case_results only for now.
            visible_weight=visible_weight,
            hidden_weight=hidden_weight,
            visible_score_percent=visible_score_percent,
            hidden_score_percent=hidden_score_percent,
            weighted_visible_contribution=weighted_visible_contribution,
            weighted_hidden_contribution=weighted_hidden_contribution,
            case_results=[c.__dict__ for c in per_case][:500],
        )
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate a student submission using predefined test packs.")
    parser.add_argument("student_file", help="Path to the student's code file (.py or .java)")
    parser.add_argument("--student-name", dest="student_name", help="Student name (default: inferred username/filename)")
    parser.add_argument("--result-file", default="result.txt", help="Output result file path")
    parser.add_argument("--problem-id", default=None, help="Problem id (default: inferred from path or add_numbers)")
    parser.add_argument(
        "--extra-hidden-cases",
        default=None,
        help="Optional JSON file containing additional hidden test cases (contract-style problems only).",
    )
    return parser.parse_args()


def _is_supported_submission(student_file: Path) -> bool:
    return student_file.suffix.lower() in {".py", ".java", ".js", ".cpp", ".cc", ".cxx", ".c"}


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
        anti_cheat=raw.get("anti_cheat", {}),
    )


def _merge_extra_hidden_cases(config: ProblemConfig, extra_hidden_cases_path: Path) -> ProblemConfig:
    """Append additional hidden cases from a generator output JSON file.

    Expected format:
      { "problem_id": "...", "cases": [[...], ...] }
    """
    try:
        raw = json.loads(extra_hidden_cases_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Invalid extra hidden cases file: {extra_hidden_cases_path} ({exc})")
    cases = raw.get("cases")
    if not isinstance(cases, list):
        raise RuntimeError("Extra hidden cases file missing 'cases' list")
    extra: list[list[object]] = []
    for item in cases:
        if isinstance(item, list):
            extra.append(item)
    if not extra:
        return config

    return ProblemConfig(
        problem_id=config.problem_id,
        default_language=config.default_language,
        scoring=config.scoring,
        python_visible_test=config.python_visible_test,
        python_hidden_test=config.python_hidden_test,
        java_contract=config.java_contract,
        java_visible_cases=config.java_visible_cases,
        java_hidden_cases=[*config.java_hidden_cases, *extra],
        anti_cheat=config.anti_cheat,
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
    case_results = summary.case_results or []

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
    if case_results:
        content += "Test Case Results:\n"
        for item in case_results[:50]:
            try:
                vis = item.get("visibility")
                passed = item.get("passed")
                err = item.get("error")
                content += f"- {vis} passed={passed} error={err}\n"
            except Exception:
                continue
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
        "case_results": summary.case_results or [],
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


def _run_python_anti_cheat(student_file: Path, anti_cheat_cfg: dict[str, object] | None = None) -> list[str]:
    cfg = anti_cheat_cfg or {}
    python_cfg = cfg.get("python", {}) if isinstance(cfg, dict) else {}
    disallowed_import_roots = {"os", "subprocess", "socket", "requests", "http", "urllib"}
    disallowed_import_roots.update(set(python_cfg.get("disallowed_import_roots", [])))
    disallowed_calls = {"eval", "exec", "compile", "__import__"}
    disallowed_calls.update(set(python_cfg.get("disallowed_calls", [])))
    disallowed_nodes = set(python_cfg.get("disallowed_ast_nodes", []))
    violations: list[str] = []

    source = student_file.read_text(encoding="utf-8", errors="replace")
    source = source.lstrip("\ufeff")
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
        if type(node).__name__ in disallowed_nodes:
            violations.append(f"Disallowed AST node: {type(node).__name__}")

    seen: set[str] = set()
    unique_violations: list[str] = []
    for item in violations:
        if item not in seen:
            seen.add(item)
            unique_violations.append(item)
    return unique_violations


def _run_java_anti_cheat(student_file: Path, anti_cheat_cfg: dict[str, object] | None = None) -> list[str]:
    cfg = anti_cheat_cfg or {}
    java_cfg = cfg.get("java", {}) if isinstance(cfg, dict) else {}
    disallowed_patterns = [
        r"\bProcessBuilder\b",
        r"\bRuntime\s*\.\s*getRuntime\s*\(",
        r"\bSystem\s*\.\s*exit\s*\(",
        r"\bjava\.net\b",
        r"\bjava\.nio\.file\b",
    ]
    disallowed_patterns.extend(list(java_cfg.get("disallowed_patterns", [])))
    source = student_file.read_text(encoding="utf-8", errors="replace")
    source = source.lstrip("\ufeff")
    violations: list[str] = []
    for pattern in disallowed_patterns:
        if re.search(pattern, source):
            violations.append(f"Disallowed Java usage matched pattern: {pattern}")
    return violations


def _run_javascript_anti_cheat(student_file: Path, anti_cheat_cfg: dict[str, object] | None = None) -> list[str]:
    cfg = anti_cheat_cfg or {}
    js_cfg = cfg.get("javascript", {}) if isinstance(cfg, dict) else {}
    disallowed_patterns = [
        r"\brequire\s*\(\s*['\"]fs['\"]\s*\)",
        r"\brequire\s*\(\s*['\"]child_process['\"]\s*\)",
        r"\brequire\s*\(\s*['\"]net['\"]\s*\)",
        r"\brequire\s*\(\s*['\"]http['\"]\s*\)",
        r"\bprocess\s*\.\s*exit\b",
    ]
    disallowed_patterns.extend(list(js_cfg.get("disallowed_patterns", [])))
    source = student_file.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")
    violations: list[str] = []
    for pattern in disallowed_patterns:
        if re.search(pattern, source):
            violations.append(f"Disallowed JS usage matched pattern: {pattern}")
    return violations


def _run_cpp_anti_cheat(student_file: Path, anti_cheat_cfg: dict[str, object] | None = None) -> list[str]:
    cfg = anti_cheat_cfg or {}
    cpp_cfg = cfg.get("cpp", {}) if isinstance(cfg, dict) else {}
    disallowed_patterns = [
        r"\bstd::filesystem\b",
        r"#\s*include\s*<filesystem>",
        r"\bsystem\s*\(",
        r"\bfork\s*\(",
    ]
    disallowed_patterns.extend(list(cpp_cfg.get("disallowed_patterns", [])))
    source = student_file.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")
    violations: list[str] = []
    for pattern in disallowed_patterns:
        if re.search(pattern, source):
            violations.append(f"Disallowed C++ usage matched pattern: {pattern}")
    return violations


def _normalize_source_for_fingerprint(source: str, language: str) -> str:
    if language == "python":
        source = re.sub(r"#.*", "", source)
    elif language == "java":
        source = re.sub(r"//.*", "", source)
        source = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    elif language in {"cpp", "c"}:
        source = re.sub(r"//.*", "", source)
        source = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    elif language == "javascript":
        source = re.sub(r"//.*", "", source)
        source = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    source = re.sub(r"\s+", "", source)
    return source.lower()


def _compute_fingerprint(student_file: Path, language: str) -> str:
    source = student_file.read_text(encoding="utf-8", errors="replace")
    source = source.lstrip("\ufeff")
    normalized = _normalize_source_for_fingerprint(source, language)
    import hashlib

    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _tokenize_source(source: str, language: str) -> list[str]:
    if language == "python":
        source = re.sub(r"#.*", "", source)
    elif language == "java":
        source = re.sub(r"//.*", "", source)
        source = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    elif language in {"c", "cpp", "javascript"}:
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


def _js_expected_string(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _evaluate_javascript_cases(student_file: Path, method_name: str, cases: list[list[object]], mode: str | None) -> tuple[int, int]:
    if shutil.which("node") is None:
        raise RuntimeError("Node.js runtime not found (node).")

    passed = 0
    total = 0
    temp_dir = Path(tempfile.mkdtemp(prefix="js_eval_"))
    try:
        harness = temp_dir / "harness.js"
        harness.write_text(
            "\n".join(
                [
                    "const submissionPath = process.argv[2];",
                    "const funcName = process.argv[3];",
                    "const argsJson = process.argv[4];",
                    "let mod;",
                    "try { mod = require(submissionPath); } catch (e) { console.error('IMPORT_ERROR:' + e.toString()); process.exit(2); }",
                    "const fn = mod[funcName] || mod.default || mod;",
                    "if (typeof fn !== 'function') { console.error('MISSING_FUNCTION:' + funcName); process.exit(3); }",
                    "let args;",
                    "try { args = JSON.parse(argsJson); } catch (e) { console.error('BAD_ARGS'); process.exit(4); }",
                    "try {",
                    "  const out = fn.apply(null, args);",
                    "  if (out === undefined) { console.log(''); } else { console.log(String(out)); }",
                    "} catch (e) { console.error('RUNTIME_ERROR:' + e.toString()); process.exit(5); }",
                ]
            ),
            encoding="utf-8",
        )

        submission_abs = str(student_file.resolve())
        for row in cases:
            total += 1
            if mode == "string_unary":
                inp = _js_expected_string(row[0])
                expected = _js_expected_string(row[1])
                args = [inp]
            else:
                a = row[0]
                b = row[1]
                expected = row[2]
                args = [a, b]
            cp = subprocess.run(
                ["node", str(harness), submission_abs, method_name, json.dumps(args)],
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
            if cp.returncode != 0:
                continue
            actual = (cp.stdout or "").strip()
            if mode == "string_unary":
                if actual == expected.strip():
                    passed += 1
            else:
                try:
                    actual_f = float(actual)
                    expected_f = float(expected)  # type: ignore[arg-type]
                except ValueError:
                    continue
                if abs(actual_f - expected_f) <= 1e-9:
                    passed += 1
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
    return passed, total


def _evaluate_javascript(student_file: Path, config: ProblemConfig) -> TestSummary:
    contract = config.java_contract or {}
    method_name = str(contract.get("method_name") or "solve")
    mode = contract.get("mode") if isinstance(contract.get("mode"), str) else None
    visible_passed, visible_total = _evaluate_javascript_cases(student_file, method_name, config.java_visible_cases, mode)
    hidden_passed, hidden_total = _evaluate_javascript_cases(student_file, method_name, config.java_hidden_cases, mode)

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


def _evaluate_cpp_cases(student_file: Path, function_name: str, cases: list[list[object]], mode: str | None) -> tuple[int, int]:
    if shutil.which("g++") is None:
        raise RuntimeError("C++ compiler not found (g++).")

    passed = 0
    total = 0
    temp_dir = Path(tempfile.mkdtemp(prefix="cpp_eval_"))
    try:
        submission_name = "submission.cpp"
        submission_cpp = temp_dir / submission_name
        submission_cpp.write_text(student_file.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff"), encoding="utf-8")

        harness_cpp = temp_dir / "harness.cpp"
        if mode == "string_unary":
            harness_cpp.write_text(
                "\n".join(
                    [
                        "#include <iostream>",
                        "#include <string>",
                        f"#include \"{submission_name}\"",
                        "int main() {",
                        "  std::string input;",
                        "  std::getline(std::cin, input);",
                        f"  std::string out = {function_name}(input);",
                        "  std::cout << out;",
                        "  return 0;",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )
        else:
            harness_cpp.write_text(
                "\n".join(
                    [
                        "#include <iostream>",
                        f"#include \"{submission_name}\"",
                        "int main() {",
                        "  double a, b;",
                        "  if (!(std::cin >> a >> b)) return 1;",
                        f"  auto out = {function_name}(a, b);",
                        "  std::cout << out;",
                        "  return 0;",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )

        exe_path = temp_dir / ("run.exe" if os.name == "nt" else "run")
        cp = subprocess.run(
            ["g++", "-std=c++17", "-O2", str(harness_cpp), "-o", str(exe_path)],
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
        )
        if cp.returncode != 0:
            raise RuntimeError(f"C++ compile failed: {cp.stderr.strip()}")

        for row in cases:
            total += 1
            if mode == "string_unary":
                inp = _js_expected_string(row[0])
                expected = _js_expected_string(row[1])
                stdin_data = inp
            else:
                a = row[0]
                b = row[1]
                expected = row[2]
                stdin_data = f"{a} {b}"
            cp2 = subprocess.run(
                [str(exe_path)],
                input=stdin_data,
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
            if cp2.returncode != 0:
                continue
            actual = (cp2.stdout or "").strip()
            if mode == "string_unary":
                if actual == expected.strip():
                    passed += 1
            else:
                try:
                    actual_f = float(actual)
                    expected_f = float(expected)  # type: ignore[arg-type]
                except ValueError:
                    continue
                if abs(actual_f - expected_f) <= 1e-9:
                    passed += 1
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
    return passed, total


def _evaluate_cpp(student_file: Path, config: ProblemConfig) -> TestSummary:
    contract = config.java_contract or {}
    function_name = str(contract.get("method_name") or "solve")
    mode = contract.get("mode") if isinstance(contract.get("mode"), str) else None
    visible_passed, visible_total = _evaluate_cpp_cases(student_file, function_name, config.java_visible_cases, mode)
    hidden_passed, hidden_total = _evaluate_cpp_cases(student_file, function_name, config.java_hidden_cases, mode)

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


def _evaluate_c_cases(student_file: Path, function_name: str, cases: list[list[object]], mode: str | None) -> tuple[int, int]:
    """C contract-style evaluation (limited).

    For robust cross-language evaluation, prefer IO-style assignments stored in DB test_cases.
    """
    if shutil.which("gcc") is None:
        raise RuntimeError("C compiler not found (gcc).")

    passed = 0
    total = 0
    temp_dir = Path(tempfile.mkdtemp(prefix="c_eval_"))
    try:
        submission_c = temp_dir / "submission.c"
        submission_c.write_text(student_file.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff"), encoding="utf-8")

        harness_c = temp_dir / "harness.c"
        if mode == "string_unary":
            # Expect: const char* <function>(const char* in);
            harness_c.write_text(
                "\n".join(
                    [
                        "#include <stdio.h>",
                        "#include <string.h>",
                        'extern const char* ' + function_name + '(const char* in);',
                        "int main(int argc, char** argv) {",
                        "  if (argc < 3) return 2;",
                        "  const char* in = argv[1];",
                        "  const char* expected = argv[2];",
                        "  const char* out = " + function_name + "(in);",
                        "  if (!out) return 3;",
                        "  if (strcmp(out, expected) == 0) { printf(\"PASS\\n\"); return 0; }",
                        "  printf(\"FAIL\\n\"); return 1;",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )
        else:
            # Expect: double <function>(double a, double b);
            harness_c.write_text(
                "\n".join(
                    [
                        "#include <stdio.h>",
                        "#include <stdlib.h>",
                        "#include <math.h>",
                        "extern double " + function_name + "(double a, double b);",
                        "int main(int argc, char** argv) {",
                        "  if (argc < 4) return 2;",
                        "  double a = atof(argv[1]);",
                        "  double b = atof(argv[2]);",
                        "  double expected = atof(argv[3]);",
                        "  double out = " + function_name + "(a, b);",
                        "  if (fabs(out - expected) <= 1e-9) { printf(\"PASS\\n\"); return 0; }",
                        "  printf(\"FAIL\\n\"); return 1;",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )

        exe = temp_dir / "prog"
        cp = subprocess.run(
            ["gcc", "-O2", "-std=c11", submission_c.name, harness_c.name, "-lm", "-o", exe.name],
            cwd=temp_dir,
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        if cp.returncode != 0:
            raise RuntimeError(cp.stderr or cp.stdout or "C compilation failed.")

        for case in cases:
            if not isinstance(case, list) or len(case) < 2:
                continue
            total += 1
            if mode == "string_unary":
                raw_in = str(case[0])
                expected = str(case[1])
                args = [str(exe), raw_in, expected]
            else:
                a = float(case[0])
                b = float(case[1])
                expected = float(case[2]) if len(case) > 2 else 0.0
                args = [str(exe), str(a), str(b), str(expected)]
            cp2 = subprocess.run(args, cwd=temp_dir, capture_output=True, text=True, check=False, timeout=5)
            if cp2.returncode == 0:
                passed += 1
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
    return passed, total


def _evaluate_c(student_file: Path, config: ProblemConfig) -> TestSummary:
    contract = config.java_contract or {}
    function_name = str(contract.get("method_name") or "solve")
    mode = contract.get("mode") if isinstance(contract.get("mode"), str) else None
    visible_passed, visible_total = _evaluate_c_cases(student_file, function_name, config.java_visible_cases, mode)
    hidden_passed, hidden_total = _evaluate_c_cases(student_file, function_name, config.java_hidden_cases, mode)

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
    extra_hidden_cases_path: Path | None = None,
) -> int:
    repo_root = _get_repo_root()
    suffix = student_file.suffix.lower()
    if suffix == ".py":
        language = "python"
    elif suffix == ".java":
        language = "java"
    elif suffix == ".js":
        language = "javascript"
    elif suffix == ".c":
        language = "c"
    else:
        language = "cpp"
    username = _infer_username(student_file)

    # Coding-interview style IO testcases (from SQLite DB). If present, prefer this mode.
    try:
        from assignment_intel.testcases import load_io_test_cases

        io_cases = load_io_test_cases(problem_id)
    except Exception:
        io_cases = []

    if io_cases:
        try:
            summary = _evaluate_io_cases(language=language, student_file=student_file, cases=io_cases)
        except (RuntimeError, subprocess.TimeoutExpired, ValueError) as exc:
            print(f"Error: {exc}")
            return 1

        summary.anti_cheat_passed = True
        summary.anti_cheat_violations = []
        summary.plagiarism_detected = False
        summary.plagiarism_matches = []
        summary.plagiarism_risk_score = 0.0
        summary.plagiarism_evidence = []
        _write_result(result_file=result_file, student_name=student_name, problem_id=problem_id, language=language, summary=summary)
        json_path = _write_result_json(result_file=result_file, student_name=student_name, problem_id=problem_id, language=language, summary=summary)
        print(f"Result saved to: {result_file}")
        print(f"Result JSON saved to: {json_path}")
        return 0

    try:
        config = _load_problem_config(problem_id)
        if extra_hidden_cases_path and extra_hidden_cases_path.exists() and language != "python":
            config = _merge_extra_hidden_cases(config, extra_hidden_cases_path)
    except RuntimeError as exc:
        print(f"Error: {exc}")
        return 1

    try:
        if language == "python":
            violations = _run_python_anti_cheat(student_file, config.anti_cheat)
        elif language == "java":
            violations = _run_java_anti_cheat(student_file, config.anti_cheat)
        elif language == "javascript":
            violations = _run_javascript_anti_cheat(student_file, config.anti_cheat)
        else:
            violations = _run_cpp_anti_cheat(student_file, config.anti_cheat)
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
        elif language == "java":
            summary = _evaluate_java(student_file, config)
        elif language == "javascript":
            summary = _evaluate_javascript(student_file, config)
        elif language == "c":
            summary = _evaluate_c(student_file, config)
        else:
            summary = _evaluate_cpp(student_file, config)
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

    extra_hidden = Path(args.extra_hidden_cases).resolve() if args.extra_hidden_cases else None
    return evaluate_student(
        student_file=student_file,
        student_name=student_name,
        result_file=result_file,
        problem_id=problem_id,
        extra_hidden_cases_path=extra_hidden,
    )


if __name__ == "__main__":
    raise SystemExit(main())
