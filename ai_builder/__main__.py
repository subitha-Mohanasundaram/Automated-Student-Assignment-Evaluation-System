"""
AI Workflow Builder CLI
=======================
Entry point: python -m ai_builder

Modes:
  python -m ai_builder chat                          # Interactive mode
  python -m ai_builder build "GitHub PR → Slack"     # Build from CLI
  python -m ai_builder explain my_workflow.json
  python -m ai_builder check  my_workflow.json
  python -m ai_builder estimate my_workflow.json
  python -m ai_builder suggest my_workflow.json
  python -m ai_builder diagram my_workflow.json
  python -m ai_builder edit my_workflow.json "Add retry to all action nodes"
  python -m ai_builder review my_workflow.json       # Full build+review
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ai_builder.builder import WorkflowBuilder
from ai_builder.chat import BuilderChat


# ANSI
_BOLD  = "\033[1m"
_CYAN  = "\033[96m"
_GREEN = "\033[92m"
_RED   = "\033[91m"
_DIM   = "\033[2m"
_RESET = "\033[0m"


def _load_workflow(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _save_if_requested(wf: dict, path: str, output: str = None) -> None:
    dest = output or path
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(wf, f, indent=2)
    print(f"\n{_GREEN}✅ Saved to {dest}{_RESET}")


def cmd_chat(args: argparse.Namespace, builder: WorkflowBuilder) -> int:
    chat = BuilderChat(builder=builder)
    chat.run()
    return 0


def cmd_build(args: argparse.Namespace, builder: WorkflowBuilder) -> int:
    intent = args.intent
    print(f"{_DIM}🔨 Generating workflow...{_RESET}")
    result = builder.build(intent)
    if not result.success:
        print(f"{_RED}❌ {result.error}{_RESET}", file=sys.stderr)
        return 1
    print(f"\n{_GREEN}{_BOLD}✅ Workflow: {result.name}{_RESET}")
    print(f"   Nodes   : {result.node_count}")
    print(f"   Plugins : {', '.join(result.plugins_used) or 'auto'}")
    print(f"\n{_CYAN}Explanation:{_RESET}")
    print(f"  {result.explanation}")

    if args.output:
        _save_if_requested(result.workflow_json, args.output, args.output)
    elif args.print_json:
        print("\n" + json.dumps(result.workflow_json, indent=2))

    if args.full:
        _run_full_review(builder, result.workflow_json)

    print(f"\n{_DIM}Session cost: ${builder.session_cost_usd:.4f}{_RESET}")
    return 0


def cmd_explain(args: argparse.Namespace, builder: WorkflowBuilder) -> int:
    wf     = _load_workflow(args.workflow)
    print(f"{_DIM}📖 Explaining...{_RESET}")
    result = builder.explain(wf)
    if not result.success:
        print(f"{_RED}❌ {result.error}{_RESET}", file=sys.stderr)
        return 1
    print(f"\n{_CYAN}{_BOLD}📖 {wf.get('name', 'Workflow')}{_RESET}")
    print(f"\n{result.summary}")
    if result.steps:
        print(f"\n{_BOLD}Steps:{_RESET}")
        for i, s in enumerate(result.steps, 1):
            print(f"  {i}. {s}")
    if result.data_flow:
        print(f"\n{_BOLD}Data Flow:{_RESET}\n  {result.data_flow}")
    if result.prerequisites:
        print(f"\n{_BOLD}Prerequisites:{_RESET}")
        for p in result.prerequisites:
            print(f"  • {p}")
    return 0


def cmd_check(args: argparse.Namespace, builder: WorkflowBuilder) -> int:
    wf     = _load_workflow(args.workflow)
    print(f"{_DIM}🔍 Checking...{_RESET}")
    result = builder.diagnose(wf)
    if not result.success:
        print(f"{_RED}❌ {result.error}{_RESET}", file=sys.stderr)
        return 1
    score_color = _GREEN if result.health_score >= 80 else "\033[93m" if result.health_score >= 50 else _RED
    print(f"\n{_BOLD}Health Score: {score_color}{result.health_score:.0f}/100{_RESET}  —  {result.summary}")
    if not result.issues:
        print(f"  {_GREEN}✅ No issues!{_RESET}")
        return 0
    for issue in result.issues:
        sev_icon = {"error": "❌", "warning": "⚠️ ", "info": "ℹ️ "}.get(issue.severity, "•")
        node_tag = f" [{issue.node_id}]" if issue.node_id else ""
        print(f"\n  {sev_icon} [{issue.code}]{node_tag}")
        print(f"     {issue.message}")
        print(f"     {_DIM}→ {issue.suggestion}{_RESET}")
    return 1 if result.error_count > 0 else 0


def cmd_estimate(args: argparse.Namespace, builder: WorkflowBuilder) -> int:
    wf     = _load_workflow(args.workflow)
    rpd    = args.runs_per_day
    print(f"{_DIM}💰 Estimating ({rpd} runs/day)...{_RESET}")
    result = builder.estimate(wf, runs_per_day=rpd)
    if not result.success:
        print(f"{_RED}❌ {result.error}{_RESET}", file=sys.stderr)
        return 1
    print(f"\n{_BOLD}💰 Cost & Runtime — {wf.get('name')}{_RESET}")
    print(result.summary_text())
    return 0


def cmd_suggest(args: argparse.Namespace, builder: WorkflowBuilder) -> int:
    wf     = _load_workflow(args.workflow)
    print(f"{_DIM}💡 Generating suggestions...{_RESET}")
    result = builder.suggest(wf)
    if not result.success:
        print(f"{_RED}❌ {result.error}{_RESET}", file=sys.stderr)
        return 1
    print(f"\n{_BOLD}💡 Suggestions — {wf.get('name')}{_RESET}")
    print(f"  {result.summary}")
    for s in result.suggestions:
        prio_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(s.priority, "•")
        auto_tag  = f"  {_GREEN}[auto]{_RESET}" if s.auto_applicable else ""
        print(f"\n  {prio_icon} [{s.category}] {_BOLD}{s.title}{_RESET}{auto_tag}")
        print(f"     {s.description}")
        print(f"     {_DIM}→ {s.action}{_RESET}")
        if s.estimated_impact:
            print(f"     Impact: {s.estimated_impact}")
    return 0


def cmd_diagram(args: argparse.Namespace, builder: WorkflowBuilder) -> int:
    wf     = _load_workflow(args.workflow)
    print(f"{_DIM}🏗️  Generating architecture...{_RESET}")
    result = builder.architecture(wf)
    if not result.success:
        print(f"{_RED}❌ {result.error}{_RESET}", file=sys.stderr)
        return 1

    if args.format in ("mermaid", "all"):
        print(f"\n{_CYAN}=== Mermaid Flowchart ==={_RESET}")
        print("```mermaid")
        print(result.mermaid)
        print("```")

    if args.format in ("ascii", "all"):
        print(f"\n{_CYAN}=== ASCII Diagram ==={_RESET}")
        print(result.ascii_art)

    if args.format in ("text", "all"):
        print(f"\n{_CYAN}=== Architecture Description ==={_RESET}")
        print(result.description)

    if args.output:
        out = {
            "mermaid":     result.mermaid,
            "ascii":       result.ascii_art,
            "description": result.description,
            "components":  result.components,
            "data_flows":  result.data_flows,
        }
        with open(args.output, "w") as f:
            json.dump(out, f, indent=2)
        print(f"\n{_GREEN}✅ Saved architecture to {args.output}{_RESET}")
    return 0


def cmd_edit(args: argparse.Namespace, builder: WorkflowBuilder) -> int:
    wf      = _load_workflow(args.workflow)
    command = args.command
    print(f"{_DIM}✏️  Applying: {command[:70]}...{_RESET}")
    result  = builder.edit(wf, command)
    if not result.success:
        print(f"{_RED}❌ {result.error}{_RESET}", file=sys.stderr)
        return 1
    print(f"\n{_GREEN}✅ Edit applied!{_RESET}")
    print(f"  Parsed as: {result.command_parsed}")
    for c in result.changes:
        print(f"  • {c}")
    print(f"\n{result.diff_summary}")
    out = args.output or args.workflow
    _save_if_requested(result.updated_workflow, args.workflow, out)
    return 0


def cmd_review(args: argparse.Namespace, builder: WorkflowBuilder) -> int:
    wf = _load_workflow(args.workflow)
    _run_full_review(builder, wf)
    return 0


def _run_full_review(builder: WorkflowBuilder, wf: dict) -> None:
    """Print a complete review of a workflow."""
    name = wf.get("name", "Workflow")
    print(f"\n{'='*60}")
    print(f"  📋  Full Review: {name}")
    print(f"{'='*60}")

    # Explain
    print(f"\n{_CYAN}📖 Explanation{_RESET}")
    ex = builder.explain(wf)
    if ex.success:
        print(f"  {ex.summary}")

    # Diagnose
    print(f"\n{_CYAN}🔍 Health Check{_RESET}")
    diag = builder.diagnose(wf)
    if diag.success:
        print(f"  Score: {diag.health_score:.0f}/100  —  {diag.summary}")

    # Estimate
    print(f"\n{_CYAN}💰 Estimates{_RESET}")
    est = builder.estimate(wf)
    if est.success:
        print(f"  Cost/run: ${est.cost_per_run_usd:.5f}   Runtime: {est.estimated_runtime_ms}ms")

    # Suggestions
    print(f"\n{_CYAN}💡 Suggestions{_RESET}")
    sug = builder.suggest(wf)
    if sug.success and sug.suggestions:
        for s in sug.suggestions[:3]:
            prio = f"[{s.priority.upper()}]"
            print(f"  {prio} {s.title}")
    elif sug.success:
        print("  ✨ No major improvements needed!")

    # Architecture
    print(f"\n{_CYAN}🏗️  Architecture{_RESET}")
    arch = builder.architecture(wf)
    if arch.success:
        print(arch.ascii_art)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog        = "python -m ai_builder",
        description = "AI Workflow Builder — Phase 7",
        formatter_class = argparse.RawDescriptionHelpFormatter,
        epilog = """\
Examples:
  python -m ai_builder chat
  python -m ai_builder build "GitHub PR merged → Slack + Jira" -o pr_workflow.json
  python -m ai_builder build "Daily weather to email" --full
  python -m ai_builder explain workflows/examples/01_google_form_to_sheets.workflow.json
  python -m ai_builder check  workflows/examples/02_github_to_slack.workflow.json
  python -m ai_builder estimate workflows/examples/04_incident_monitoring.workflow.json --runs-per-day 1000
  python -m ai_builder suggest workflows/examples/03_weather_to_email.workflow.json
  python -m ai_builder diagram workflows/examples/01_google_form_to_sheets.workflow.json --format all
  python -m ai_builder edit my_workflow.json "Add retry to all action nodes"
  python -m ai_builder review workflows/examples/05_document_ai_pipeline.workflow.json
    """,
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # --- chat ---
    sub.add_parser("chat", help="Launch interactive chat mode")

    # --- build ---
    p_build = sub.add_parser("build", help="Build a workflow from natural language")
    p_build.add_argument("intent", help="Natural language workflow description")
    p_build.add_argument("-o", "--output", help="Save generated workflow JSON to this file")
    p_build.add_argument("--print-json", action="store_true", help="Print workflow JSON to stdout")
    p_build.add_argument("--full", action="store_true", help="Run full review after build")

    # --- explain ---
    p_exp = sub.add_parser("explain", help="Explain a workflow in plain English")
    p_exp.add_argument("workflow", help="Path to workflow JSON file")

    # --- check ---
    p_chk = sub.add_parser("check", help="Detect mistakes and issues in a workflow")
    p_chk.add_argument("workflow", help="Path to workflow JSON file")

    # --- estimate ---
    p_est = sub.add_parser("estimate", help="Estimate cost and runtime")
    p_est.add_argument("workflow", help="Path to workflow JSON file")
    p_est.add_argument("--runs-per-day", type=int, default=100, dest="runs_per_day")

    # --- suggest ---
    p_sug = sub.add_parser("suggest", help="Get improvement suggestions")
    p_sug.add_argument("workflow", help="Path to workflow JSON file")

    # --- diagram ---
    p_dia = sub.add_parser("diagram", help="Generate architecture diagrams")
    p_dia.add_argument("workflow", help="Path to workflow JSON file")
    p_dia.add_argument("--format", choices=["mermaid", "ascii", "text", "all"], default="all")
    p_dia.add_argument("-o", "--output", help="Save diagram JSON to this file")

    # --- edit ---
    p_edi = sub.add_parser("edit", help="Edit a workflow with a natural language command")
    p_edi.add_argument("workflow", help="Path to workflow JSON file")
    p_edi.add_argument("command",  help="Natural language edit command")
    p_edi.add_argument("-o", "--output", help="Save to a different file (default: overwrite)")

    # --- review ---
    p_rev = sub.add_parser("review", help="Run a full review of a workflow")
    p_rev.add_argument("workflow", help="Path to workflow JSON file")

    # Global options
    parser.add_argument("--model",  default="gpt-4o-mini", help="OpenAI model to use")
    parser.add_argument("--verbose",action="store_true")

    args    = parser.parse_args()
    builder = WorkflowBuilder(model=args.model, verbose=args.verbose)

    import logging
    logging.basicConfig(level=logging.WARNING)

    handlers = {
        "chat":     cmd_chat,
        "build":    cmd_build,
        "explain":  cmd_explain,
        "check":    cmd_check,
        "estimate": cmd_estimate,
        "suggest":  cmd_suggest,
        "diagram":  cmd_diagram,
        "edit":     cmd_edit,
        "review":   cmd_review,
    }

    h = handlers.get(args.command)
    if h:
        sys.exit(h(args, builder))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
