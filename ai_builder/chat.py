"""
Interactive Chat Interface
==========================
Rich multi-turn conversation loop for the AI Workflow Builder.
Maintains workflow state across turns and routes commands to
the correct builder method.

Commands the chat understands (all in natural language):
  build  / create  → WorkflowBuilder.build()
  explain          → WorkflowBuilder.explain()
  review / check   → WorkflowBuilder.diagnose()
  estimate / cost  → WorkflowBuilder.estimate()
  suggest          → WorkflowBuilder.suggest()
  edit / change    → WorkflowBuilder.edit()
  diagram / arch   → WorkflowBuilder.architecture()
  save             → WorkflowBuilder.save()
  load             → WorkflowBuilder.load()
  show / print     → print current workflow JSON
  clear / reset    → clear current workflow
  help             → show this list
  exit / quit      → exit
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from ai_builder.builder import WorkflowBuilder

# ANSI colors
_CYAN    = "\033[96m"
_GREEN   = "\033[92m"
_YELLOW  = "\033[93m"
_RED     = "\033[91m"
_BLUE    = "\033[94m"
_MAGENTA = "\033[95m"
_BOLD    = "\033[1m"
_DIM     = "\033[2m"
_RESET   = "\033[0m"

_BANNER = f"""{_CYAN}{_BOLD}
╔══════════════════════════════════════════════════════════════╗
║          🤖  AI Workflow Builder  —  Phase 7                 ║
║              Automation Platform · Powered by GPT            ║
╠══════════════════════════════════════════════════════════════╣
║  Type a workflow description to generate one, or:            ║
║  'explain'  'check'  'estimate'  'suggest'  'diagram'        ║
║  'edit <command>'  'save <path>'  'load <path>'  'help'      ║
╚══════════════════════════════════════════════════════════════╝
{_RESET}"""

_HELP = f"""
{_BOLD}Available Commands:{_RESET}
  {_CYAN}build{_RESET}    Create a new workflow from natural language description
  {_CYAN}explain{_RESET}  Explain the current workflow in plain English
  {_CYAN}check{_RESET}    Find mistakes and issues in the current workflow
  {_CYAN}estimate{_RESET} Estimate cost and runtime of the current workflow
  {_CYAN}suggest{_RESET}  Get AI improvement suggestions
  {_CYAN}diagram{_RESET}  Generate Mermaid and ASCII architecture diagrams
  {_CYAN}edit{_RESET}     Edit with natural language (e.g. 'edit Add retry to fetch node')
  {_CYAN}save{_RESET}     Save current workflow JSON (e.g. 'save my_workflow.json')
  {_CYAN}load{_RESET}     Load a workflow from file (e.g. 'load my_workflow.json')
  {_CYAN}show{_RESET}     Print the current workflow JSON
  {_CYAN}clear{_RESET}    Clear current workflow and start fresh
  {_CYAN}cost{_RESET}     Show current AI session token/cost usage
  {_CYAN}help{_RESET}     Show this help
  {_CYAN}exit{_RESET}     Exit the builder

{_BOLD}Example workflow descriptions:{_RESET}
  • "When a GitHub PR is merged, post a message to #releases in Slack"
  • "Every morning at 9am, fetch weather for London and email the team"
  • "When a new Google Form response arrives, validate and save to Sheets, then notify on Slack"
  • "Monitor incident alerts from PagerDuty and auto-create GitHub issues"
"""


class BuilderChat:
    """Interactive multi-turn chat loop for the AI Workflow Builder."""

    def __init__(self, builder: Optional[WorkflowBuilder] = None, verbose: bool = False) -> None:
        self._builder  = builder or WorkflowBuilder(verbose=verbose)
        self._workflow: Optional[Dict[str, Any]] = None
        self._history:  List[str] = []
        self._verbose   = verbose

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Start the interactive chat loop."""
        print(_BANNER)
        while True:
            try:
                user_input = input(f"{_BOLD}{_BLUE}You ▶ {_RESET}").strip()
            except (EOFError, KeyboardInterrupt):
                print(f"\n{_DIM}Goodbye!{_RESET}")
                break

            if not user_input:
                continue

            self._history.append(user_input)
            self._dispatch(user_input)

    def _dispatch(self, user_input: str) -> None:
        """Route input to the correct handler."""
        lower = user_input.lower().strip()

        if lower in ("exit", "quit", "bye"):
            self._print_cost_summary()
            print(f"{_DIM}Goodbye!{_RESET}")
            sys.exit(0)

        elif lower in ("help", "?", "h"):
            print(_HELP)

        elif lower in ("clear", "reset", "new"):
            self._workflow = None
            self._print_ok("Workflow cleared. Ready for a new one!")

        elif lower in ("show", "print", "json"):
            self._cmd_show()

        elif lower in ("explain", "describe", "what does it do"):
            self._cmd_explain()

        elif lower in ("check", "review", "diagnose", "validate", "lint"):
            self._cmd_diagnose()

        elif lower in ("estimate", "cost", "price", "how much", "runtime"):
            self._cmd_estimate()

        elif lower in ("suggest", "improve", "optimize", "suggestions"):
            self._cmd_suggest()

        elif lower in ("diagram", "arch", "architecture", "mermaid", "flowchart"):
            self._cmd_architecture()

        elif lower in ("session", "usage", "tokens"):
            self._print_cost_summary()

        elif lower.startswith("edit ") or lower.startswith("change ") or lower.startswith("modify "):
            command = re.sub(r"^(edit|change|modify)\s+", "", user_input, flags=re.IGNORECASE).strip()
            self._cmd_edit(command)

        elif lower.startswith("save "):
            path = user_input.split(None, 1)[1].strip()
            self._cmd_save(path)

        elif lower.startswith("load "):
            path = user_input.split(None, 1)[1].strip()
            self._cmd_load(path)

        elif lower.startswith("estimate "):
            self._cmd_estimate()

        elif lower.startswith("build ") or lower.startswith("create ") or lower.startswith("generate "):
            intent = re.sub(r"^(build|create|generate)\s+", "", user_input, flags=re.IGNORECASE).strip()
            self._cmd_build(intent)

        else:
            # Heuristic: if there's a workflow loaded and input looks like an edit
            edit_keywords = ["add", "remove", "move", "replace", "rename", "wrap", "set", "delete", "insert", "put", "change"]
            if self._workflow and any(lower.startswith(kw) for kw in edit_keywords):
                self._cmd_edit(user_input)
            else:
                # Treat as a build intent
                self._cmd_build(user_input)

    # ------------------------------------------------------------------
    # Command handlers
    # ------------------------------------------------------------------

    def _cmd_build(self, intent: str) -> None:
        if not intent:
            self._print_warn("Please describe what the workflow should do.")
            return
        print(f"{_DIM}  🔨 Generating workflow...{_RESET}")
        result = self._builder.build(intent)
        if not result.success:
            self._print_error(f"Generation failed: {result.error}")
            return
        self._workflow = result.workflow_json
        print(f"\n{_GREEN}{_BOLD}✅ Workflow Generated!{_RESET}")
        print(f"  {_BOLD}Name{_RESET}     : {result.name}")
        print(f"  {_BOLD}ID{_RESET}       : {result.workflow_id}")
        print(f"  {_BOLD}Nodes{_RESET}    : {result.node_count}")
        print(f"  {_BOLD}Plugins{_RESET}  : {', '.join(result.plugins_used) or 'auto-detected'}")
        print(f"  {_BOLD}Confidence{_RESET}: {result.confidence:.0%}")
        print()
        print(f"{_CYAN}📖 Explanation:{_RESET}")
        print(f"  {result.explanation}")
        print()
        self._print_tip("Type 'check' to detect issues, 'estimate' for costs, or 'diagram' for a flowchart.")

    def _cmd_explain(self) -> None:
        wf = self._require_workflow()
        if not wf:
            return
        print(f"{_DIM}  📖 Generating explanation...{_RESET}")
        result = self._builder.explain(wf)
        if not result.success:
            self._print_error(f"Explain failed: {result.error}")
            return
        print(f"\n{_CYAN}{_BOLD}📖 Workflow Explanation{_RESET}")
        print(f"\n{result.summary}")
        if result.steps:
            print(f"\n{_BOLD}Step by Step:{_RESET}")
            for i, step in enumerate(result.steps, 1):
                print(f"  {i}. {step}")
        if result.data_flow:
            print(f"\n{_BOLD}Data Flow:{_RESET}")
            print(f"  {result.data_flow}")
        if result.prerequisites:
            print(f"\n{_BOLD}Prerequisites:{_RESET}")
            for p in result.prerequisites:
                print(f"  • {p}")

    def _cmd_diagnose(self) -> None:
        wf = self._require_workflow()
        if not wf:
            return
        print(f"{_DIM}  🔍 Checking workflow...{_RESET}")
        result = self._builder.diagnose(wf)
        if not result.success:
            self._print_error(f"Diagnose failed: {result.error}")
            return

        score_color = _GREEN if result.health_score >= 80 else _YELLOW if result.health_score >= 50 else _RED
        print(f"\n{_BOLD}🏥 Health Report{_RESET}  —  {score_color}Score: {result.health_score:.0f}/100{_RESET}")
        print(f"  {result.summary}")
        print()
        if not result.issues:
            print(f"  {_GREEN}✅ No issues found!{_RESET}")
            return

        # Group by severity
        for severity, icon, color in [("error", "❌", _RED), ("warning", "⚠️ ", _YELLOW), ("info", "ℹ️ ", _BLUE)]:
            group = [i for i in result.issues if i.severity == severity]
            if group:
                print(f"{color}{_BOLD}{icon} {severity.title()}s ({len(group)}){_RESET}")
                for issue in group:
                    node_tag = f" [{issue.node_id}]" if issue.node_id else ""
                    print(f"  {color}•{_RESET} {issue.message}{_DIM}{node_tag}{_RESET}")
                    print(f"    {_DIM}→ {issue.suggestion}{_RESET}")
                    if issue.auto_fixable:
                        print(f"    {_GREEN}  ✨ Auto-fixable — type 'edit Fix {issue.code.lower().replace('_',' ')}'{_RESET}")
                print()

    def _cmd_estimate(self) -> None:
        wf = self._require_workflow()
        if not wf:
            return
        print(f"{_DIM}  💰 Estimating cost and runtime...{_RESET}")
        result = self._builder.estimate(wf)
        if not result.success:
            self._print_error(f"Estimate failed: {result.error}")
            return

        print(f"\n{_BOLD}💰 Cost & Runtime Estimate{_RESET}")
        print(f"  {_CYAN}{'Per Run':<20}{_RESET} ${result.cost_per_run_usd:.5f}")
        print(f"  {_CYAN}{'Per Day':<20}{_RESET} ${result.cost_per_day_usd:.3f}  ({result.runs_per_day} runs/day assumed)")
        print(f"  {_CYAN}{'Per Month':<20}{_RESET} ${result.cost_per_month_usd:.2f}")
        print(f"  {_CYAN}{'Runtime (total)':<20}{_RESET} {result.estimated_runtime_ms:,}ms")
        print(f"  {_CYAN}{'Critical Path':<20}{_RESET} {result.critical_path_ms:,}ms")
        print()
        print(f"  {_DIM}Breakdown: AI ${result.ai_cost_usd:.5f}  ·  API ${result.api_cost_usd:.5f}  ·  Compute ${result.compute_cost_usd:.5f}{_RESET}")
        if result.node_estimates:
            print(f"\n{_BOLD}Per-Node Breakdown:{_RESET}")
            for ne in result.node_estimates:
                cost_str = f"${ne.cost_usd_per_run:.5f}"
                rt_str   = f"{ne.runtime_ms}ms"
                note     = f"  {_DIM}({ne.notes}){_RESET}" if ne.notes else ""
                print(f"  {ne.node_id:<30} {cost_str:<14} {rt_str}{note}")
        print()
        print(f"  {_DIM}Assumptions: {' · '.join(result.assumptions[:3])}{_RESET}")

    def _cmd_suggest(self) -> None:
        wf = self._require_workflow()
        if not wf:
            return
        print(f"{_DIM}  💡 Generating suggestions...{_RESET}")
        result = self._builder.suggest(wf)
        if not result.success:
            self._print_error(f"Suggest failed: {result.error}")
            return

        print(f"\n{_BOLD}💡 Improvement Suggestions{_RESET}")
        print(f"  {result.summary}")
        print()
        if not result.suggestions:
            print(f"  {_GREEN}✨ Workflow is already well-optimized!{_RESET}")
            return

        for s in result.suggestions:
            pcolor = _RED if s.priority == "high" else _YELLOW if s.priority == "medium" else _DIM
            cicon  = {"performance": "⚡", "reliability": "🛡️", "cost": "💰", "security": "🔒", "ux": "✨"}.get(s.category, "💡")
            print(f"  {pcolor}[{s.priority.upper()}]{_RESET} {cicon} {_BOLD}{s.title}{_RESET}")
            print(f"    {s.description}")
            print(f"    {_DIM}Apply with: edit {s.action}{_RESET}")
            if s.estimated_impact:
                print(f"    {_GREEN}Impact: {s.estimated_impact}{_RESET}")
            if s.auto_applicable:
                print(f"    {_CYAN}✨ Auto-applicable{_RESET}")
            print()

    def _cmd_edit(self, command: str) -> None:
        wf = self._require_workflow()
        if not wf:
            return
        if not command:
            self._print_warn("Please provide an edit command (e.g. 'edit Add retry to fetch node')")
            return
        print(f"{_DIM}  ✏️  Applying edit: {command[:60]}...{_RESET}")
        result = self._builder.edit(wf, command)
        if not result.success:
            self._print_error(f"Edit failed: {result.error}")
            return
        self._workflow = result.updated_workflow
        print(f"\n{_GREEN}{_BOLD}✅ Edit Applied!{_RESET}")
        print(f"  {_BOLD}Parsed as:{_RESET} {result.command_parsed}")
        if result.changes:
            print(f"\n  {_BOLD}Changes:{_RESET}")
            for change in result.changes:
                print(f"    • {change}")
        if result.diff_summary:
            print(f"\n{_DIM}{result.diff_summary}{_RESET}")

    def _cmd_architecture(self) -> None:
        wf = self._require_workflow()
        if not wf:
            return
        print(f"{_DIM}  🏗️  Generating architecture...{_RESET}")
        result = self._builder.architecture(wf)
        if not result.success:
            self._print_error(f"Architecture generation failed: {result.error}")
            return

        print(f"\n{_BOLD}🏗️  Architecture{_RESET}")
        print(f"\n{_CYAN}— ASCII Diagram ————————————————————————————{_RESET}")
        print(result.ascii_art)
        print(f"\n{_CYAN}— Mermaid Flowchart (copy to GitHub/Notion) ——{_RESET}")
        print("```mermaid")
        print(result.mermaid)
        print("```")
        if result.description:
            print(f"\n{_CYAN}— Architecture Description ————————————————{_RESET}")
            print(result.description)

    def _cmd_show(self) -> None:
        wf = self._require_workflow()
        if not wf:
            return
        print(f"\n{_BOLD}Current Workflow JSON:{_RESET}")
        print(json.dumps(wf, indent=2))

    def _cmd_save(self, path: str) -> None:
        wf = self._require_workflow()
        if not wf:
            return
        if not path.endswith(".json"):
            path += ".json"
        try:
            self._builder.save(wf, path)
            self._print_ok(f"Saved to {path}")
        except Exception as exc:
            self._print_error(str(exc))

    def _cmd_load(self, path: str) -> None:
        try:
            self._workflow = self._builder.load(path)
            self._print_ok(f"Loaded workflow: {self._workflow.get('name', path)}")
        except Exception as exc:
            self._print_error(str(exc))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _require_workflow(self) -> Optional[Dict[str, Any]]:
        if not self._workflow:
            self._print_warn("No workflow loaded. Describe a workflow to build one, or use 'load <path>'.")
        return self._workflow

    def _print_ok(self, msg: str) -> None:
        print(f"  {_GREEN}✅ {msg}{_RESET}")

    def _print_warn(self, msg: str) -> None:
        print(f"  {_YELLOW}⚠️  {msg}{_RESET}")

    def _print_error(self, msg: str) -> None:
        print(f"  {_RED}❌ {msg}{_RESET}")

    def _print_tip(self, msg: str) -> None:
        print(f"  {_DIM}💡 {msg}{_RESET}")

    def _print_cost_summary(self) -> None:
        cost   = self._builder.session_cost_usd
        tokens = self._builder.session_tokens
        print(f"\n{_DIM}Session: {tokens['input']:,} input + {tokens['output']:,} output tokens  ·  ${cost:.4f} total{_RESET}")
