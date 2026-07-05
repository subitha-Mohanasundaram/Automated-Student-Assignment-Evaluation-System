"""
Tool implementations for the CodeMentor ReAct Agent.

Each function here is a REAL tool — it actually executes code, parses ASTs,
queries ChromaDB, and matches error patterns. The agent calls these autonomously.

Tools:
    get_problem_spec(problem_id)
    run_visible_tests(code, problem_id, language)
    analyze_code_structure(code, language)
    check_error_pattern(error_type, actual, expected)
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


# ── TOOL 1: get_problem_spec ──────────────────────────────────────────────────

def get_problem_spec(problem_id: str) -> dict[str, Any]:
    """Fetch the full problem specification from ChromaDB / problem.json.

    Returns title, description, constraints, sample I/O cases.
    """
    try:
        from rag.retrieve import get_problem_context
        context_text = get_problem_context(problem_id)
    except Exception as exc:
        context_text = f"Could not retrieve spec: {exc}"

    # Also try loading raw problem.json for richer data
    problems_dir = Path(__file__).parent.parent / "problems"
    raw_path = problems_dir / problem_id / "problem.json"
    raw: dict = {}
    if raw_path.exists():
        try:
            raw = json.loads(raw_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    visible_cases: list[dict] = []
    java_visible = raw.get("java", {}).get("visible_cases", [])
    for case in java_visible[:3]:
        if isinstance(case, list) and len(case) >= 2:
            visible_cases.append({"input": str(case[0]), "expected": str(case[1])})

    return {
        "problem_id": problem_id,
        "title": raw.get("title") or problem_id.replace("_", " ").title(),
        "description": raw.get("description") or context_text,
        "constraints": raw.get("constraints") or "",
        "default_language": raw.get("default_language", "python"),
        "sample_cases": visible_cases,
        "context_text": context_text,
    }


# ── TOOL 2: run_visible_tests ─────────────────────────────────────────────────

def run_visible_tests(code: str, problem_id: str, language: str = "python") -> dict[str, Any]:
    """Re-execute the student's code against visible test cases.

    Runs each visible case, captures actual output, compares to expected.
    Returns per-case pass/fail with input, expected, actual, error.
    """
    problems_dir = Path(__file__).parent.parent / "problems"
    raw_path = problems_dir / problem_id / "problem.json"

    if not raw_path.exists():
        return {"error": f"problem.json not found for {problem_id}", "cases": []}

    try:
        raw = json.loads(raw_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"error": f"Could not load problem.json: {exc}", "cases": []}

    java_section = raw.get("java", {})
    contract_mode = java_section.get("contract", {}).get("mode", "")
    contract_method = java_section.get("contract", {}).get("method_name", "solve")
    visible_cases = java_section.get("visible_cases", [])

    if not visible_cases:
        return {"error": "No visible test cases defined in problem.json", "cases": []}

    if language.lower() == "python":
        # Use actual function name from student code, not contract's Java name
        method_name = _detect_python_function(code, contract_method)
        return _run_python_contract_cases(
            code=code,
            cases=visible_cases,
            mode=contract_mode,
            method_name=method_name,
        )

    return {"error": "run_visible_tests only supports Python currently", "cases": []}


def _detect_python_function(code: str, fallback: str) -> str:
    """Extract the first function name from Python code via AST."""
    try:
        tree = ast.parse(code.lstrip("\ufeff"))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                return node.name
    except Exception:
        pass
    return fallback


def _run_python_contract_cases(
    code: str,
    cases: list,
    mode: str,
    method_name: str,
) -> dict[str, Any]:
    """Run Python code against contract-style cases via subprocess."""
    results = []
    passed_count = 0

    with tempfile.TemporaryDirectory(prefix="mentor_tool_") as tmp:
        tmp_path = Path(tmp)
        sub_file = tmp_path / "submission.py"
        sub_file.write_text(code.lstrip("\ufeff"), encoding="utf-8")

        runner = tmp_path / "runner.py"

        if mode == "string_unary":
            # fn(string_input) -> string
            runner.write_text(
                "import sys, importlib.util\n"
                "spec = importlib.util.spec_from_file_location('sub', sys.argv[1])\n"
                "mod = importlib.util.module_from_spec(spec)\n"
                "spec.loader.exec_module(mod)\n"
                "fn = getattr(mod, sys.argv[2], None)\n"
                "if fn is None: print('ERROR:missing_function'); sys.exit(1)\n"
                "inp = sys.argv[3]\n"
                "try:\n"
                "    out = fn(inp)\n"
                "    print(str(out) if out is not None else '')\n"
                "except Exception as e:\n"
                "    print(f'ERROR:{e}'); sys.exit(1)\n",
                encoding="utf-8",
            )
        else:
            # double_binary or default: fn(a, b) -> number
            # cases are [a, b, expected] triples
            runner.write_text(
                "import sys, importlib.util\n"
                "spec = importlib.util.spec_from_file_location('sub', sys.argv[1])\n"
                "mod = importlib.util.module_from_spec(spec)\n"
                "spec.loader.exec_module(mod)\n"
                "fn = getattr(mod, sys.argv[2], None)\n"
                "if fn is None: print('ERROR:missing_function'); sys.exit(1)\n"
                "a, b = float(sys.argv[3]), float(sys.argv[4])\n"
                "try:\n"
                "    out = fn(a, b)\n"
                "    print(str(out) if out is not None else '')\n"
                "except Exception as e:\n"
                "    print(f'ERROR:{e}'); sys.exit(1)\n",
                encoding="utf-8",
            )

        for case in cases[:4]:  # cap at 4 visible cases
            if not isinstance(case, list) or len(case) < 2:
                continue

            if mode == "string_unary":
                inp = str(case[0])
                expected = str(case[1]).strip()
                run_args = [sys.executable, str(runner), str(sub_file), method_name, inp]
            else:
                # double_binary: [a, b, expected]
                if len(case) < 3:
                    continue
                a, b, expected_val = float(case[0]), float(case[1]), float(case[2])
                inp = f"{a}, {b}"
                expected = str(expected_val)
                run_args = [sys.executable, str(runner), str(sub_file), method_name,
                            str(a), str(b)]

            try:
                cp = subprocess.run(
                    run_args,
                    capture_output=True, text=True, timeout=5,
                )
                actual = (cp.stdout or "").strip()
                error_msg = (cp.stderr or "").strip() if cp.returncode != 0 else ""

                # Numeric comparison for double_binary
                if mode != "string_unary" and actual and not actual.startswith("ERROR"):
                    try:
                        passed = abs(float(actual) - float(expected)) < 1e-9
                    except ValueError:
                        passed = actual == expected
                else:
                    passed = (cp.returncode == 0) and (actual == expected)

            except subprocess.TimeoutExpired:
                actual = ""
                error_msg = "timeout"
                passed = False

            if passed:
                passed_count += 1

            results.append({
                "input": inp,
                "expected": expected,
                "actual": actual,
                "passed": passed,
                "error": error_msg or ("wrong_answer" if not passed and not error_msg else ""),
            })

    total = len(results)
    return {
        "passed": passed_count,
        "total": total,
        "pass_rate": f"{passed_count}/{total}",
        "cases": results,
    }


# ── TOOL 3: analyze_code_structure ───────────────────────────────────────────

def analyze_code_structure(code: str, language: str = "python") -> dict[str, Any]:
    """AST-based analysis of the student's code.

    Detects: loop patterns, operator usage, off-by-one risks,
    missing return, recursion, common structural mistakes.
    """
    if language.lower() != "python":
        return _analyze_non_python(code, language)

    findings: list[str] = []
    suspicions: list[str] = []
    summary: dict[str, Any] = {}

    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return {"error": f"Syntax error: {exc}", "findings": [], "suspicions": []}

    # Function names
    funcs = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
    summary["functions"] = funcs

    # Operators used in return statements
    return_ops: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Return) and node.value:
            for child in ast.walk(node.value):
                if isinstance(child, ast.BinOp):
                    op_name = type(child.op).__name__
                    return_ops.append(op_name)
    summary["return_operators"] = return_ops
    if "Sub" in return_ops:
        suspicions.append("Return statement uses subtraction (Sub) — may be wrong operator")
    if "Mult" in return_ops:
        suspicions.append("Return statement uses multiplication — verify this is intended")

    # Loop analysis
    for_loops = list(ast.walk(tree))
    nested_loops = 0
    loop_ranges: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.For):
            for child in ast.walk(node):
                if isinstance(child, ast.For) and child is not node:
                    nested_loops += 1
            if isinstance(node.iter, ast.Call):
                if isinstance(node.iter.func, ast.Name) and node.iter.func.id == "range":
                    args = node.iter.args
                    if len(args) == 1:
                        loop_ranges.append("range(n) — starts at 0")
                    elif len(args) == 2:
                        a0 = ast.unparse(args[0]) if hasattr(ast, "unparse") else "?"
                        loop_ranges.append(f"range({a0}, n)")
    summary["nested_for_loops"] = nested_loops
    summary["loop_ranges"] = loop_ranges
    if nested_loops > 0:
        findings.append(f"Has {nested_loops} nested for-loop(s) — O(n²) complexity")
    if any("starts at 0" in r for r in loop_ranges) and nested_loops > 0:
        suspicions.append(
            "Inner loop starts at 0 not i+1 — this allows self-pairing (same index twice)"
        )

    # Check for early return vs always iterating
    has_early_return = False
    for node in ast.walk(tree):
        if isinstance(node, (ast.For, ast.While)):
            for child in ast.walk(node):
                if isinstance(child, ast.Return):
                    has_early_return = True
    summary["has_early_return_in_loop"] = has_early_return

    # Check for missing return
    for func in ast.walk(tree):
        if not isinstance(func, ast.FunctionDef):
            continue
        has_return = any(isinstance(n, ast.Return) and n.value for n in ast.walk(func))
        if not has_return:
            suspicions.append(f"Function '{func.name}' has no return statement with a value")

    # Off-by-one: check range comparisons
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            for op in node.ops:
                if isinstance(op, ast.Lt) and any(
                    isinstance(c, ast.Subscript) for c in ast.walk(node)
                ):
                    findings.append("Index comparison with '<' found — verify boundary")

    # Check if code uses a seen/visited dict (good pattern for two-sum style)
    uses_dict_lookup = any(
        isinstance(n, ast.Dict) or (
            isinstance(n, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id in ("seen", "visited", "lookup", "memo")
                for t in ast.walk(n)
            )
        )
        for n in ast.walk(tree)
    )
    summary["uses_hash_map"] = uses_dict_lookup
    if not uses_dict_lookup and nested_loops > 0:
        findings.append(
            "Uses nested loops without a hash map — could be O(n²) where O(n) is possible"
        )

    return {
        "summary": summary,
        "findings": findings,
        "suspicions": suspicions,
        "total_lines": len(code.splitlines()),
    }


def _analyze_non_python(code: str, language: str) -> dict[str, Any]:
    """Lightweight regex-based analysis for non-Python languages."""
    findings: list[str] = []
    suspicions: list[str] = []

    if language in ("java", "javascript", "cpp", "c"):
        # Check for nested loops
        nested = len(re.findall(r"\bfor\b", code))
        if nested >= 2:
            findings.append(f"Found {nested} for-loops — possible nested O(n²) structure")

        # Check return with minus
        if re.search(r"return\s+\w+\s*-\s*\w+", code):
            suspicions.append("Return statement uses subtraction — may be wrong operator")

        # Check for common off-by-one
        if re.search(r"for.*=\s*0.*<.*length", code):
            findings.append("Loop from 0 to length — verify inner loop bounds")

    return {
        "summary": {"language": language},
        "findings": findings,
        "suspicions": suspicions,
        "total_lines": len(code.splitlines()),
    }


# ── TOOL 4: check_error_pattern ──────────────────────────────────────────────

# Registry of known error patterns mapped to root causes and hints
_ERROR_PATTERNS: list[dict[str, str]] = [
    {
        "pattern": "wrong_answer",
        "actual_sign": "negative",
        "category": "wrong_operator",
        "description": "Output is negative when positive expected — likely subtraction instead of addition",
        "hint": "Check the operator in your return or computation statement",
    },
    {
        "pattern": "wrong_answer",
        "actual_clue": "same_index_twice",
        "category": "self_pairing",
        "description": "Output returns same index twice (e.g. '0 0') — inner loop allows i==j pairing",
        "hint": "Make the inner loop start from i+1 to avoid pairing an element with itself",
    },
    {
        "pattern": "wrong_answer",
        "actual_clue": "off_by_one",
        "category": "off_by_one",
        "description": "Output is consistently 1 more or less than expected — off-by-one error",
        "hint": "Check your loop boundary conditions and index calculations",
    },
    {
        "pattern": "timeout",
        "category": "infinite_loop_or_slow",
        "description": "Code did not finish within the time limit — likely infinite loop or O(n³+) complexity",
        "hint": "Check for loops that never terminate or consider a more efficient algorithm",
    },
    {
        "pattern": "wrong_answer",
        "actual_clue": "empty_output",
        "category": "missing_return",
        "description": "Function returns empty string or None — missing return statement or unreachable return",
        "hint": "Ensure every code path in your function ends with a return statement",
    },
    {
        "pattern": "wrong_answer",
        "actual_clue": "reversed",
        "category": "reversed_output",
        "description": "Output indices or characters are in wrong order",
        "hint": "Check the order in which you build or return your result",
    },
]


def check_error_pattern(
    error_type: str,
    actual: str,
    expected: str,
) -> dict[str, Any]:
    """Match the observed error against a registry of known coding mistake patterns.

    Returns the most likely mistake category, description, and a targeted hint.
    """
    error_type = (error_type or "wrong_answer").strip().lower()
    actual = (actual or "").strip()
    expected = (expected or "").strip()

    matches: list[dict] = []

    for pat in _ERROR_PATTERNS:
        if pat["pattern"] != error_type and error_type not in pat["pattern"]:
            continue

        score = 1  # base match on error type

        # Check actual output clues
        clue = pat.get("actual_clue", "")
        if clue == "negative":
            try:
                if float(actual) < 0 and float(expected) > 0:
                    score += 3
            except (ValueError, TypeError):
                pass
        elif clue == "same_index_twice":
            parts = actual.split()
            if len(parts) == 2 and parts[0] == parts[1]:
                score += 4
        elif clue == "off_by_one":
            try:
                diff = abs(float(actual) - float(expected))
                if 0.9 < diff < 1.1:
                    score += 3
            except (ValueError, TypeError):
                # Try string length diff
                if abs(len(actual) - len(expected)) == 1:
                    score += 2
        elif clue == "empty_output":
            if actual == "" or actual == "None":
                score += 4
        elif clue == "reversed":
            if actual and expected and actual == expected[::-1]:
                score += 4
        elif error_type == "timeout":
            score += 3

        matches.append({**pat, "_score": score})

    if not matches:
        return {
            "category": "unknown",
            "description": f"Error type '{error_type}' with no pattern match found",
            "hint": "Review your logic carefully against the visible test cases",
            "confidence": 0.3,
        }

    best = max(matches, key=lambda x: x["_score"])
    confidence = min(0.95, best["_score"] / 7.0)

    return {
        "category": best["category"],
        "description": best["description"],
        "hint": best["hint"],
        "confidence": round(confidence, 2),
        "all_matches": [
            {"category": m["category"], "score": m["_score"]}
            for m in sorted(matches, key=lambda x: -x["_score"])[:3]
        ],
    }


# ── Groq function-calling schemas ─────────────────────────────────────────────

GROQ_TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "get_problem_spec",
            "description": (
                "Fetch the full problem specification including title, description, "
                "constraints, and sample input/output cases. Call this first to understand "
                "what the problem expects before analyzing the student's code."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "problem_id": {
                        "type": "string",
                        "description": "The problem identifier, e.g. 'add_numbers' or 'two_sum'",
                    }
                },
                "required": ["problem_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_visible_tests",
            "description": (
                "Re-execute the student's code against the visible test cases for the problem. "
                "Returns each case with input, expected output, actual output, and pass/fail. "
                "Call this to see exactly what the code produces vs what is expected."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "The full student source code to execute",
                    },
                    "problem_id": {
                        "type": "string",
                        "description": "The problem identifier",
                    },
                    "language": {
                        "type": "string",
                        "description": "Programming language: 'python', 'java', 'javascript'",
                        "default": "python",
                    },
                },
                "required": ["code", "problem_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_code_structure",
            "description": (
                "Perform AST-level static analysis of the student's code. "
                "Detects: wrong operators in return statements, nested loops (O(n²)), "
                "off-by-one loop bounds, missing return paths, self-pairing patterns, "
                "and whether a hash map is used. Call this to pinpoint the faulty section."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "The full student source code to analyze",
                    },
                    "language": {
                        "type": "string",
                        "description": "Programming language: 'python', 'java', 'cpp'",
                        "default": "python",
                    },
                },
                "required": ["code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_error_pattern",
            "description": (
                "Match the observed test failure against a registry of known coding mistake patterns. "
                "Returns the most likely mistake category (e.g. wrong_operator, self_pairing, "
                "off_by_one, timeout, missing_return) and a targeted hint. "
                "Call this when you have the actual vs expected output from a failing test case."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "error_type": {
                        "type": "string",
                        "description": "The error type string: 'wrong_answer', 'timeout', 'runtime_error'",
                    },
                    "actual": {
                        "type": "string",
                        "description": "The actual output the student's code produced",
                    },
                    "expected": {
                        "type": "string",
                        "description": "The expected correct output",
                    },
                },
                "required": ["error_type", "actual", "expected"],
            },
        },
    },
]


# ── Tool dispatcher ────────────────────────────────────────────────────────────

TOOL_FUNCTIONS: dict[str, Any] = {
    "get_problem_spec": get_problem_spec,
    "run_visible_tests": run_visible_tests,
    "analyze_code_structure": analyze_code_structure,
    "check_error_pattern": check_error_pattern,
}


def dispatch_tool(name: str, arguments: dict) -> dict:
    """Execute a tool by name with the given arguments. Returns a result dict."""
    fn = TOOL_FUNCTIONS.get(name)
    if fn is None:
        return {"error": f"Unknown tool: {name}"}
    try:
        result = fn(**arguments)
        return result if isinstance(result, dict) else {"result": result}
    except Exception as exc:
        return {"error": f"Tool '{name}' raised: {exc}"}
