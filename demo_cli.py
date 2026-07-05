"""
=============================================================
  Assignment Intelligence Platform — Terminal Demo
=============================================================
Runs the full pipeline for a student submission and prints
every stage result directly in the terminal.

Usage:
    python demo_cli.py                        # uses default failing submission
    python demo_cli.py --file <path.py>       # use your own file
    python demo_cli.py --problem add_numbers  # choose problem
    python demo_cli.py --student "Your Name"  # set student name
=============================================================
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

# ── Colours ──────────────────────────────────────────────────────────────────
RED    = "\033[91m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RESET  = "\033[0m"

def _sep(char="─", n=60):
    print(f"{DIM}{char * n}{RESET}")

def _header(title: str):
    print()
    _sep("═")
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    _sep("═")

def _step(n: int, title: str):
    print(f"\n{BOLD}{YELLOW}  STEP {n}: {title}{RESET}")
    _sep()

def _ok(msg: str):   print(f"  {GREEN}✔{RESET}  {msg}")
def _fail(msg: str): print(f"  {RED}✘{RESET}  {msg}")
def _info(msg: str): print(f"  {CYAN}→{RESET}  {msg}")
def _dim(msg: str):  print(f"  {DIM}{msg}{RESET}")


# ── .env loader ───────────────────────────────────────────────────────────────
def _load_env():
    env_path = Path(".env")
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

# ── Argument parsing ──────────────────────────────────────────────────────────
def _parse():
    p = argparse.ArgumentParser(description="Assignment Intelligence Platform — Terminal Demo")
    p.add_argument("--file",    default="examples/add_numbers_fail.py", help="Path to student submission")
    p.add_argument("--problem", default="add_numbers",                  help="Problem ID")
    p.add_argument("--student", default="Alice",                        help="Student name")
    p.add_argument("--passing", action="store_true",                    help="Run a passing submission instead")
    return p.parse_args()


# ── Main demo ─────────────────────────────────────────────────────────────────
def main():
    _load_env()
    args = _parse()

    # If --passing flag, swap to the correct solution
    student_file = Path(args.file)
    if args.passing:
        student_file = Path("examples/student_ok.py")

    if not student_file.exists():
        print(f"{RED}Error: file not found: {student_file}{RESET}")
        sys.exit(1)

    _header("ASSIGNMENT INTELLIGENCE PLATFORM — FULL PIPELINE DEMO")
    _info(f"Student     : {args.student}")
    _info(f"Problem     : {args.problem}")
    _info(f"Submission  : {student_file}")
    print()
    print(f"  {BOLD}Student's code:{RESET}")
    code = student_file.read_text(encoding="utf-8")
    for line in code.strip().splitlines():
        _dim(f"    {line}")

    # ── STEP 1: Run evaluator ─────────────────────────────────────────────────
    _step(1, "Running evaluator (test sandbox)")
    result_txt  = Path("result.txt")
    result_json = Path("result.json")

    # Clear previous results
    result_txt.write_text("", encoding="utf-8")
    result_json.write_text("{}", encoding="utf-8")

    cmd = [
        sys.executable, "evaluator.py",
        str(student_file),
        "--student-name", args.student,
        "--result-file",  str(result_txt),
        "--problem-id",   args.problem,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

    if proc.stdout.strip():
        for line in proc.stdout.strip().splitlines():
            _dim(f"    {line}")

    if proc.returncode != 0:
        _fail(f"Evaluator exited with code {proc.returncode}")
        if proc.stderr.strip():
            print(f"{RED}{proc.stderr.strip()[:500]}{RESET}")
        sys.exit(1)

    if not result_json.exists() or result_json.stat().st_size < 5:
        _fail("result.json was not produced. Check evaluator output above.")
        sys.exit(1)

    result = json.loads(result_json.read_text(encoding="utf-8"))
    _ok("Evaluation complete")

    # ── STEP 2: Print score report ────────────────────────────────────────────
    _step(2, "Evaluation Results")

    score        = float(result.get("score", 0.0))
    passed       = int(result.get("passed_cases", 0))
    total        = int(result.get("total_test_cases", 0))
    visible      = result.get("visible", {})
    hidden       = result.get("hidden", {})
    anti_cheat   = result.get("anti_cheat", {})
    plagiarism   = result.get("plagiarism", {})
    case_results = result.get("case_results") or []

    score_color = GREEN if score >= 90 else (YELLOW if score >= 60 else RED)
    print(f"\n  {BOLD}Score     :{RESET} {score_color}{BOLD}{score}%{RESET}")
    print(f"  {BOLD}Tests     :{RESET}  Passed {passed}/{total}")
    print(f"  {BOLD}Visible   :{RESET}  {int(visible.get('passed',0))}/{int(visible.get('total',0))}  "
          f"({visible.get('score_percent',0)}%  →  {visible.get('weighted_contribution',0)} pts)")
    print(f"  {BOLD}Hidden    :{RESET}  {int(hidden.get('passed',0))}/{int(hidden.get('total',0))}  "
          f"({hidden.get('score_percent',0)}%  →  {hidden.get('weighted_contribution',0)} pts)")

    ac_status = anti_cheat.get("passed", True)
    print(f"  {BOLD}Anti-Cheat:{RESET}  {GREEN+'PASS'+RESET if ac_status else RED+'FAIL'+RESET}")
    if not ac_status:
        for v in (anti_cheat.get("violations") or []):
            _fail(f"    Violation: {v}")

    plag_detected = plagiarism.get("detected", False)
    print(f"  {BOLD}Plagiarism:{RESET}  {RED+'DETECTED'+RESET if plag_detected else GREEN+'CLEAR'+RESET}  "
          f"(risk score: {plagiarism.get('risk_score', 0.0)})")

    # Show visible test case results
    visible_cases = [c for c in case_results if c.get("visibility") == "visible"]
    if visible_cases:
        print(f"\n  {BOLD}Visible Test Cases:{RESET}")
        print(f"  {'Status':<8} {'Input':<20} {'Expected':<15} {'Got':<15} Error")
        _sep("─", 70)
        for c in visible_cases:
            status  = f"{GREEN}PASS{RESET}" if c.get("passed") else f"{RED}FAIL{RESET}"
            inp     = str(c.get("input", ""))[:18]
            exp     = str(c.get("expected", ""))[:13]
            act     = str(c.get("actual", ""))[:13]
            err     = str(c.get("error") or "")
            print(f"  {status}     {inp:<20} {exp:<15} {act:<15} {err}")

    failing = [c for c in case_results if not c.get("passed", True)]
    hidden_fails = [c for c in failing if c.get("visibility") != "visible"]
    if hidden_fails:
        print(f"\n  {RED}{len(hidden_fails)} hidden/stress test(s) also failed (inputs not disclosed){RESET}")

    # ── STEP 3: RAG retrieval ─────────────────────────────────────────────────
    _step(3, "RAG — Retrieving problem context from ChromaDB")
    try:
        from rag.retrieve import get_problem_context
        ctx = get_problem_context(args.problem)
        _ok("Problem context retrieved")
        for line in ctx.strip().splitlines():
            _dim(f"    {line}")
    except Exception as exc:
        _fail(f"RAG retrieval failed: {exc}")
        ctx = f"Problem: {args.problem}"

    # ── STEP 4: CodeMentor ReAct Agent ───────────────────────────────────────
    _step(4, "CodeMentor Agent — ReAct Loop (Groq LLaMA 3.3-70B + Tool Calling)")

    api_key = os.environ.get("GROQ_API_KEY", "").strip()

    if score >= 100.0 and not failing:
        _ok("All tests passed — no explanation needed.")
        ai_feedback = {
            "explanation": "All test cases passed successfully.",
            "likely_cause": "N/A",
            "hint": "Great work! No issues found.",
            "root_cause": "",
            "why_hidden_fail": "",
            "confidence": 1.0,
            "tools_used": [],
            "reasoning_turns": 0,
        }
    elif not api_key:
        _fail("GROQ_API_KEY not set — skipping agent.")
        ai_feedback = None
    else:
        _info("Agent starting investigation...")
        _info("The agent will autonomously decide which tools to call.\n")

        # Monkey-patch verbose output so we can print the trace
        try:
            from agents import codementor_agent as _cm

            # Patch _log to print to terminal with colours
            original_log = _cm.CodeMentorAgent._log
            def _verbose_log(self, msg):
                print(msg)
            _cm.CodeMentorAgent._log = _verbose_log

            output = _cm.explain_failures(
                problem_id=args.problem,
                student_code=code,
                result=result,
                api_key=api_key,
                verbose=True,
            )

            _cm.CodeMentorAgent._log = original_log  # restore

            _ok(f"Agent completed in {output.reasoning_turns} turn(s)")
            _ok(f"Tools used: {output.tools_used}")

            ai_feedback = {
                "explanation":    output.explanation,
                "likely_cause":   output.likely_cause,
                "hint":           output.hint,
                "root_cause":     output.root_cause,
                "why_hidden_fail": output.why_hidden_fail,
                "confidence":     output.confidence,
                "tools_used":     output.tools_used,
                "reasoning_turns": output.reasoning_turns,
            }
        except Exception as exc:
            _fail(f"Agent error: {exc}")
            ai_feedback = None

    # ── STEP 5: Final result files ────────────────────────────────────────────
    _step(5, "Writing final result files")

    if ai_feedback:
        result["ai_feedback"] = ai_feedback
        result_json.write_text(json.dumps(result, indent=2), encoding="utf-8")
        _ok("result.json  updated with ai_feedback block")

        # Write result.txt
        txt  = f"Student Name: {result.get('student_name','')}\n"
        txt += f"Problem ID: {result.get('problem_id','')}\n"
        txt += f"Language: {result.get('language','')}\n"
        txt += f"Score: {result.get('score','')}\n"
        txt += f"Passed Cases: {result.get('passed_cases','')}\n"
        txt += f"Total Test Cases: {result.get('total_test_cases','')}\n"
        txt += f"Visible Passed: {int(visible.get('passed',0))}/{int(visible.get('total',0))}\n"
        txt += f"Hidden Passed: {int(hidden.get('passed',0))}/{int(hidden.get('total',0))}\n"
        txt += f"Anti-Cheat: {'PASS' if ac_status else 'FAIL'}\n"
        txt += f"Plagiarism: {'DETECTED' if plag_detected else 'NOT_DETECTED'}\n"
        txt += f"\nAI Feedback\n-----------\n"
        txt += f"Explanation: {ai_feedback['explanation']}\n"
        txt += f"Likely Cause: {ai_feedback['likely_cause']}\n"
        txt += f"Hint: {ai_feedback['hint']}\n"
        result_txt.write_text(txt, encoding="utf-8")
        _ok("result.txt   updated with AI Feedback section")
    else:
        _info("Skipped (no AI feedback available)")

    # ── STEP 6: Print full agent output ──────────────────────────────────────
    if ai_feedback:
        _step(6, "CodeMentor Output  (what the student receives)")
        print()
        print(f"  {BOLD}Explanation  :{RESET}")
        for line in textwrap.wrap(ai_feedback["explanation"], width=68):
            print(f"    {line}")

        print()
        print(f"  {BOLD}Likely Cause :{RESET}")
        for line in textwrap.wrap(ai_feedback["likely_cause"], width=68):
            print(f"    {line}")

        if ai_feedback.get("root_cause"):
            print()
            print(f"  {BOLD}Root Cause   :{RESET}")
            for line in textwrap.wrap(ai_feedback["root_cause"], width=68):
                print(f"    {DIM}{line}{RESET}")

        if ai_feedback.get("why_hidden_fail"):
            print()
            print(f"  {BOLD}Hidden Tests :{RESET}")
            for line in textwrap.wrap(ai_feedback["why_hidden_fail"], width=68):
                print(f"    {DIM}{line}{RESET}")

        print()
        print(f"  {BOLD}Hint         :{RESET}")
        for line in textwrap.wrap(ai_feedback["hint"], width=68):
            print(f"    {YELLOW}{line}{RESET}")

        conf = ai_feedback.get("confidence", 0)
        conf_color = GREEN if conf >= 0.8 else (YELLOW if conf >= 0.5 else RED)
        print()
        print(f"  {BOLD}Confidence   :{RESET}  {conf_color}{conf}{RESET}")
        print(f"  {BOLD}Turns taken  :{RESET}  {ai_feedback.get('reasoning_turns', '?')}")
        print(f"  {BOLD}Tools used   :{RESET}  {ai_feedback.get('tools_used', [])}")

    # ── Final summary ─────────────────────────────────────────────────────────
    _header("PIPELINE COMPLETE")
    _ok(f"result.json  →  {result_json.resolve()}")
    _ok(f"result.txt   →  {result_txt.resolve()}")
    if score >= 90:
        print(f"\n  {GREEN}{BOLD}  RESULT: PASSED  ({score}%){RESET}")
    elif score >= 60:
        print(f"\n  {YELLOW}{BOLD}  RESULT: PARTIAL  ({score}%){RESET}")
    else:
        print(f"\n  {RED}{BOLD}  RESULT: FAILED  ({score}%){RESET}")
    print()


if __name__ == "__main__":
    main()
