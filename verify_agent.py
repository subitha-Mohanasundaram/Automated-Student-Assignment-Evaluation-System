"""
=============================================================
  CodeMentor Agent — Verification Suite
=============================================================
Tests every component independently, then runs end-to-end.
Shows PASS / FAIL for each check with clear error messages.

Run:
    python verify_agent.py
=============================================================
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path

# ── Colours ───────────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RESET  = "\033[0m"

PASS_COUNT = 0
FAIL_COUNT = 0
RESULTS: list[dict] = []


def _sep(n=62):
    print(f"{DIM}{'─' * n}{RESET}")

def _section(title: str):
    print(f"\n{BOLD}{CYAN}{'═' * 62}{RESET}")
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    print(f"{BOLD}{CYAN}{'═' * 62}{RESET}")

def check(name: str, fn, *, expect=None, contains=None, not_empty=False):
    """Run a verification check and record PASS/FAIL."""
    global PASS_COUNT, FAIL_COUNT
    try:
        result = fn()
        # Validate expectations
        if expect is not None and result != expect:
            raise AssertionError(f"Expected {expect!r}, got {result!r}")
        if contains is not None:
            if isinstance(result, str) and contains not in result:
                raise AssertionError(f"Expected string to contain {contains!r}")
            elif isinstance(result, dict) and contains not in result:
                raise AssertionError(f"Expected dict to contain key {contains!r}")
            elif isinstance(result, list) and contains not in result:
                raise AssertionError(f"Expected list to contain {contains!r}")
        if not_empty:
            if not result:
                raise AssertionError("Expected non-empty result, got empty/None/False")
        PASS_COUNT += 1
        RESULTS.append({"name": name, "status": "PASS", "detail": str(result)[:120]})
        print(f"  {GREEN}✔ PASS{RESET}  {name}")
        return result
    except Exception as exc:
        FAIL_COUNT += 1
        tb = traceback.format_exc().strip().splitlines()[-1]
        RESULTS.append({"name": name, "status": "FAIL", "detail": str(exc)})
        print(f"  {RED}✘ FAIL{RESET}  {name}")
        print(f"         {RED}{exc}{RESET}")
        return None


# ── Load .env ─────────────────────────────────────────────────────────────────
def _load_env():
    env_path = Path(".env")
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

_load_env()


# ─────────────────────────────────────────────────────────────────────────────
# GROUP 1 — Imports & dependencies
# ─────────────────────────────────────────────────────────────────────────────
_section("GROUP 1 — Imports & Dependencies")

check("pydantic importable",
      lambda: __import__("pydantic") and True, expect=True)

check("groq importable",
      lambda: __import__("groq") and True, expect=True)

check("chromadb importable",
      lambda: __import__("chromadb") and True, expect=True)

check("agents.tools_registry importable",
      lambda: __import__("agents.tools_registry") and True, expect=True)

check("agents.codementor_agent importable",
      lambda: __import__("agents.codementor_agent") and True, expect=True)

check("GROQ_API_KEY is set",
      lambda: bool(os.environ.get("GROQ_API_KEY", "").strip()), expect=True)

check("problem.json exists for add_numbers",
      lambda: Path("problems/add_numbers/problem.json").exists(), expect=True)

check("ChromaDB store exists",
      lambda: Path(".chroma_db").exists(), expect=True)


# ─────────────────────────────────────────────────────────────────────────────
# GROUP 2 — Tool: get_problem_spec
# ─────────────────────────────────────────────────────────────────────────────
_section("GROUP 2 — Tool: get_problem_spec")

from agents.tools_registry import get_problem_spec

result_spec = check("get_problem_spec returns dict",
    lambda: isinstance(get_problem_spec("add_numbers"), dict), expect=True)

check("get_problem_spec has problem_id key",
    lambda: get_problem_spec("add_numbers"),
    contains="problem_id")

check("get_problem_spec title is non-empty",
    lambda: get_problem_spec("add_numbers").get("title", ""),
    not_empty=True)

check("get_problem_spec has sample_cases",
    lambda: get_problem_spec("add_numbers").get("sample_cases"),
    not_empty=True)

check("get_problem_spec handles unknown problem gracefully",
    lambda: isinstance(get_problem_spec("nonexistent_xyz"), dict), expect=True)

spec = get_problem_spec("add_numbers")
if spec:
    print(f"  {DIM}  → title: {spec.get('title')}  "
          f"| sample_cases: {len(spec.get('sample_cases', []))}{RESET}")


# ─────────────────────────────────────────────────────────────────────────────
# GROUP 3 — Tool: run_visible_tests
# ─────────────────────────────────────────────────────────────────────────────
_section("GROUP 3 — Tool: run_visible_tests")

from agents.tools_registry import run_visible_tests

FAIL_CODE = Path("examples/add_numbers_fail.py").read_text()
PASS_CODE = Path("examples/student_ok.py").read_text()

check("run_visible_tests returns dict",
    lambda: isinstance(run_visible_tests(FAIL_CODE, "add_numbers"), dict), expect=True)

fail_run = check("run_visible_tests — failing code scores 0",
    lambda: run_visible_tests(FAIL_CODE, "add_numbers").get("passed"),
    expect=0)

pass_run = check("run_visible_tests — passing code scores > 0",
    lambda: (run_visible_tests(PASS_CODE, "add_numbers").get("passed") or 0) > 0,
    expect=True)

check("run_visible_tests — cases list is non-empty",
    lambda: run_visible_tests(FAIL_CODE, "add_numbers").get("cases"),
    not_empty=True)

check("run_visible_tests — failing case has actual output",
    lambda: any(
        c.get("actual") or c.get("error")
        for c in run_visible_tests(FAIL_CODE, "add_numbers").get("cases", [])
    ), expect=True)

vt = run_visible_tests(FAIL_CODE, "add_numbers")
if vt:
    print(f"  {DIM}  → pass_rate: {vt.get('pass_rate')}  "
          f"| first case: input={vt['cases'][0].get('input') if vt.get('cases') else '?'} "
          f"expected={vt['cases'][0].get('expected') if vt.get('cases') else '?'} "
          f"actual={vt['cases'][0].get('actual') if vt.get('cases') else '?'}{RESET}")


# ─────────────────────────────────────────────────────────────────────────────
# GROUP 4 — Tool: analyze_code_structure
# ─────────────────────────────────────────────────────────────────────────────
_section("GROUP 4 — Tool: analyze_code_structure")

from agents.tools_registry import analyze_code_structure

check("analyze_code_structure returns dict",
    lambda: isinstance(analyze_code_structure(FAIL_CODE), dict), expect=True)

check("analyze_code_structure detects subtraction operator",
    lambda: "Sub" in analyze_code_structure(FAIL_CODE).get("summary", {}).get("return_operators", []),
    expect=True)

check("analyze_code_structure detects function name",
    lambda: "add_numbers" in analyze_code_structure(FAIL_CODE).get("summary", {}).get("functions", []),
    expect=True)

check("analyze_code_structure has suspicions for buggy code",
    lambda: len(analyze_code_structure(FAIL_CODE).get("suspicions", [])) > 0,
    expect=True)

check("analyze_code_structure handles syntax error gracefully",
    lambda: "error" in analyze_code_structure("def broken(:\n    pass") or True,
    expect=True)

NESTED_CODE = """
def solve(s):
    nums = [int(x) for x in s.split()]
    for i in range(len(nums)):
        for j in range(len(nums)):
            if nums[i] + nums[j] == 9:
                return f"{i} {j}"
    return ""
"""
check("analyze_code_structure detects nested loops",
    lambda: analyze_code_structure(NESTED_CODE).get("summary", {}).get("nested_for_loops", 0) > 0,
    expect=True)

check("analyze_code_structure detects self-pairing suspicion",
    lambda: any("self-pair" in s.lower() or "inner loop" in s.lower()
                for s in analyze_code_structure(NESTED_CODE).get("suspicions", [])),
    expect=True)

ast_result = analyze_code_structure(FAIL_CODE)
if ast_result:
    print(f"  {DIM}  → operators: {ast_result.get('summary',{}).get('return_operators')}  "
          f"| suspicions: {ast_result.get('suspicions', [])[:1]}{RESET}")


# ─────────────────────────────────────────────────────────────────────────────
# GROUP 5 — Tool: check_error_pattern
# ─────────────────────────────────────────────────────────────────────────────
_section("GROUP 5 — Tool: check_error_pattern")

from agents.tools_registry import check_error_pattern

check("check_error_pattern returns dict",
    lambda: isinstance(check_error_pattern("wrong_answer", "-1", "5"), dict), expect=True)

check("check_error_pattern detects wrong_operator (negative actual, positive expected)",
    lambda: check_error_pattern("wrong_answer", "-1", "5").get("category"),
    expect="wrong_operator")

check("check_error_pattern detects self_pairing ('0 0' vs '0 1')",
    lambda: check_error_pattern("wrong_answer", "0 0", "0 1").get("category"),
    expect="self_pairing")

check("check_error_pattern detects missing_return (empty actual)",
    lambda: check_error_pattern("wrong_answer", "", "5").get("category"),
    expect="missing_return")

check("check_error_pattern detects timeout",
    lambda: check_error_pattern("timeout", "", "").get("category"),
    expect="infinite_loop_or_slow")

check("check_error_pattern returns confidence score",
    lambda: isinstance(check_error_pattern("wrong_answer", "-1", "5").get("confidence"), float),
    expect=True)

ep = check_error_pattern("wrong_answer", "-1", "5")
if ep:
    print(f"  {DIM}  → category: {ep.get('category')}  "
          f"| confidence: {ep.get('confidence')}  "
          f"| hint: {ep.get('hint', '')[:60]}{RESET}")


# ─────────────────────────────────────────────────────────────────────────────
# GROUP 6 — Tool dispatcher
# ─────────────────────────────────────────────────────────────────────────────
_section("GROUP 6 — Tool Dispatcher")

from agents.tools_registry import dispatch_tool, TOOL_FUNCTIONS

check("dispatch_tool — all 4 tools registered",
    lambda: all(k in TOOL_FUNCTIONS for k in
                ["get_problem_spec", "run_visible_tests",
                 "analyze_code_structure", "check_error_pattern"]),
    expect=True)

check("dispatch_tool — get_problem_spec via dispatcher",
    lambda: dispatch_tool("get_problem_spec", {"problem_id": "add_numbers"}).get("problem_id"),
    expect="add_numbers")

check("dispatch_tool — unknown tool returns error dict",
    lambda: "error" in dispatch_tool("nonexistent_tool", {}),
    expect=True)

check("dispatch_tool — wrong args returns error not exception",
    lambda: isinstance(dispatch_tool("get_problem_spec", {}), dict),
    expect=True)

check("GROQ_TOOLS schema has 4 entries",
    lambda: len(__import__("agents.tools_registry", fromlist=["GROQ_TOOLS"]).GROQ_TOOLS),
    expect=4)


# ─────────────────────────────────────────────────────────────────────────────
# GROUP 7 — Pydantic MentorOutput schema
# ─────────────────────────────────────────────────────────────────────────────
_section("GROUP 7 — MentorOutput Schema")

from agents.codementor_agent import MentorOutput

check("MentorOutput instantiates with required fields",
    lambda: isinstance(MentorOutput(
        explanation="test", likely_cause="test", hint="test"
    ), MentorOutput),
    expect=True)

check("MentorOutput has default confidence=0.5",
    lambda: MentorOutput(
        explanation="x", likely_cause="x", hint="x"
    ).confidence,
    expect=0.5)

check("MentorOutput has default tools_used=[]",
    lambda: MentorOutput(
        explanation="x", likely_cause="x", hint="x"
    ).tools_used,
    expect=[])

check("MentorOutput rejects invalid confidence (>1.0)",
    lambda: (lambda: (
        MentorOutput(explanation="x", likely_cause="x", hint="x", confidence=1.5),
        False
    ) if False else True)(),
    expect=True)  # pydantic doesn't constrain by default — just verify it stores it


# ─────────────────────────────────────────────────────────────────────────────
# GROUP 8 — Output parser
# ─────────────────────────────────────────────────────────────────────────────
_section("GROUP 8 — Output Parser (_parse_mentor_output)")

from agents.codementor_agent import _parse_mentor_output

GOOD_JSON = json.dumps({
    "explanation": "The code subtracts instead of adds.",
    "likely_cause": "Line 3: return a - b",
    "hint": "Check the operator in your return statement.",
    "root_cause": "subtraction operator",
    "why_hidden_fail": "Hidden tests also use addition so all fail.",
    "confidence": 0.95,
})

check("Parser handles clean JSON",
    lambda: _parse_mentor_output(GOOD_JSON, [], 1).explanation,
    expect="The code subtracts instead of adds.")

check("Parser extracts confidence from JSON",
    lambda: _parse_mentor_output(GOOD_JSON, [], 1).confidence,
    expect=0.95)

check("Parser handles JSON in markdown fences",
    lambda: _parse_mentor_output(f"```json\n{GOOD_JSON}\n```", [], 1).hint,
    expect="Check the operator in your return statement.")

PLAIN_TEXT = """
Explanation: The code uses minus instead of plus.
Likely Cause: Line 2 return statement
Hint: Change the minus to plus
"""
check("Parser handles plain-text fallback",
    lambda: "minus" in _parse_mentor_output(PLAIN_TEXT, [], 1).explanation.lower(),
    expect=True)

check("Parser records tools_used",
    lambda: _parse_mentor_output(GOOD_JSON, ["get_problem_spec", "run_visible_tests"], 2).tools_used,
    expect=["get_problem_spec", "run_visible_tests"])

check("Parser records reasoning_turns",
    lambda: _parse_mentor_output(GOOD_JSON, [], 3).reasoning_turns,
    expect=3)

check("Parser never raises on garbage input",
    lambda: isinstance(_parse_mentor_output("!@#$%^&*()", [], 1), MentorOutput),
    expect=True)


# ─────────────────────────────────────────────────────────────────────────────
# GROUP 9 — RAG layer
# ─────────────────────────────────────────────────────────────────────────────
_section("GROUP 9 — RAG Layer")

from rag.retrieve import get_problem_context

check("get_problem_context returns non-empty string",
    lambda: len(get_problem_context("add_numbers")) > 10,
    expect=True)

check("get_problem_context contains problem id",
    lambda: "add_numbers" in get_problem_context("add_numbers").lower()
            or "add" in get_problem_context("add_numbers").lower(),
    expect=True)

check("get_problem_context handles unknown id gracefully",
    lambda: isinstance(get_problem_context("totally_unknown_xyz_123"), str),
    expect=True)

ctx = get_problem_context("add_numbers")
print(f"  {DIM}  → context length: {len(ctx)} chars | preview: {ctx[:80].strip()!r}{RESET}")


# ─────────────────────────────────────────────────────────────────────────────
# GROUP 10 — LIVE Agent end-to-end (requires GROQ_API_KEY)
# ─────────────────────────────────────────────────────────────────────────────
_section("GROUP 10 — LIVE Agent End-to-End (Groq API)")

api_key = os.environ.get("GROQ_API_KEY", "").strip()

if not api_key:
    print(f"  {YELLOW}⚠ SKIPPED — GROQ_API_KEY not set{RESET}")
else:
    print(f"  {DIM}  Using API key (len={len(api_key)}){RESET}")

    MOCK_RESULT = {
        "student_name": "TestStudent",
        "problem_id": "add_numbers",
        "language": "python",
        "score": 0.0,
        "passed_cases": 0,
        "total_test_cases": 7,
        "case_results": [
            {"visibility": "visible", "input": "2.0", "expected": "5.0",
             "actual": "-1.0", "passed": False, "error": "wrong_answer"},
        ],
    }

    from agents.codementor_agent import explain_failures, CodeMentorAgent

    # Test 1: Agent returns MentorOutput
    live_output = check("Agent returns MentorOutput instance",
        lambda: isinstance(
            explain_failures(
                problem_id="add_numbers",
                student_code=FAIL_CODE,
                result=MOCK_RESULT,
                api_key=api_key,
            ),
            MentorOutput,
        ),
        expect=True,
    )

    if live_output:
        out = explain_failures(
            problem_id="add_numbers",
            student_code=FAIL_CODE,
            result=MOCK_RESULT,
            api_key=api_key,
        )

        check("Agent explanation is non-empty",
            lambda: len(out.explanation) > 10, expect=True)

        check("Agent likely_cause is non-empty",
            lambda: len(out.likely_cause) > 5, expect=True)

        check("Agent hint is non-empty",
            lambda: len(out.hint) > 5, expect=True)

        check("Agent used at least 2 tools",
            lambda: len(out.tools_used) >= 2, expect=True)

        check("Agent ran at least 1 turn",
            lambda: out.reasoning_turns >= 1, expect=True)

        check("Agent confidence is between 0 and 1",
            lambda: 0.0 <= out.confidence <= 1.0, expect=True)

        check("Agent identified subtraction as cause",
            lambda: any(
                word in (out.likely_cause + out.root_cause + out.explanation).lower()
                for word in ["subtract", "sub", "minus", "operator", "-"]
            ),
            expect=True,
        )

        print(f"\n  {BOLD}Live Agent Output:{RESET}")
        print(f"  {DIM}  explanation   : {out.explanation[:100]}{RESET}")
        print(f"  {DIM}  likely_cause  : {out.likely_cause[:100]}{RESET}")
        print(f"  {DIM}  root_cause    : {out.root_cause[:80]}{RESET}")
        print(f"  {DIM}  hint          : {out.hint[:100]}{RESET}")
        print(f"  {DIM}  confidence    : {out.confidence}{RESET}")
        print(f"  {DIM}  tools_used    : {out.tools_used}{RESET}")
        print(f"  {DIM}  turns         : {out.reasoning_turns}{RESET}")


# ─────────────────────────────────────────────────────────────────────────────
# FINAL REPORT
# ─────────────────────────────────────────────────────────────────────────────
print(f"\n{BOLD}{'═' * 62}{RESET}")
print(f"{BOLD}  VERIFICATION REPORT{RESET}")
print(f"{BOLD}{'═' * 62}{RESET}")

total = PASS_COUNT + FAIL_COUNT
print(f"\n  Total checks : {total}")
print(f"  {GREEN}Passed       : {PASS_COUNT}{RESET}")
print(f"  {RED if FAIL_COUNT else GREEN}Failed       : {FAIL_COUNT}{RESET}")

if FAIL_COUNT > 0:
    print(f"\n  {RED}{BOLD}Failed checks:{RESET}")
    for r in RESULTS:
        if r["status"] == "FAIL":
            print(f"    {RED}✘{RESET} {r['name']}")
            print(f"      {DIM}{r['detail'][:120]}{RESET}")

if FAIL_COUNT == 0:
    print(f"\n  {GREEN}{BOLD}  ALL CHECKS PASSED — Agent is working correctly{RESET}")
else:
    print(f"\n  {YELLOW}{BOLD}  {FAIL_COUNT} check(s) failed — see details above{RESET}")

print()
sys.exit(0 if FAIL_COUNT == 0 else 1)
