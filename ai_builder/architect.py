"""
Architecture Generator
======================
Generates Mermaid flowcharts, ASCII diagrams, and prose architecture
descriptions from workflow JSON.

Outputs:
  - Mermaid LR flowchart (renderable in GitHub, Notion, Obsidian)
  - ASCII art box diagram
  - Structured component/data-flow description
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple

from ai_builder.ai_client import AIClient
from ai_builder.models import ArchitectureResult

# Node type → Mermaid shape
_MERMAID_SHAPES = {
    "action":         ("[", "]"),         # rectangle
    "condition":      ("{", "}"),         # diamond
    "ai":             ("([", "])"),       # stadium
    "notification":   ("[[", "]]"),       # subroutine
    "webhook":        (">", "]"),         # flag
    "parallel":       ("[/", "\\]"),      # parallelogram
    "loop":           ("[(", ")]"),       # cylinder
    "human_approval": ("{{", "}}"),       # hexagon
    "delay":          ("[", "]"),
    "transform":      ("[", "]"),
    "subworkflow":    ("[[", "]]"),
}

# Node type → color class
_MERMAID_STYLES = {
    "action":         "fill:#4A90D9,color:#fff,stroke:#2d6ca0",
    "condition":      "fill:#F5A623,color:#fff,stroke:#c4841c",
    "ai":             "fill:#10a37f,color:#fff,stroke:#0d856a",
    "notification":   "fill:#9B59B6,color:#fff,stroke:#7d3c98",
    "webhook":        "fill:#E67E22,color:#fff,stroke:#ca6f1e",
    "parallel":       "fill:#1ABC9C,color:#fff,stroke:#17a589",
    "loop":           "fill:#3498DB,color:#fff,stroke:#2980b9",
    "human_approval": "fill:#E74C3C,color:#fff,stroke:#c0392b",
    "delay":          "fill:#95A5A6,color:#fff,stroke:#7f8c8d",
    "transform":      "fill:#2ECC71,color:#fff,stroke:#27ae60",
}


class ArchitectureGenerator:
    """Generates multiple representations of a workflow's architecture."""

    def __init__(self, client: AIClient) -> None:
        self._ai = client

    def generate(self, workflow_json: Dict[str, Any]) -> ArchitectureResult:
        """Generate all architecture representations."""
        try:
            mermaid     = self._generate_mermaid(workflow_json)
            ascii_art   = self._generate_ascii(workflow_json)
            description = self._generate_description(workflow_json)
            components  = self._extract_components(workflow_json)
            data_flows  = self._extract_data_flows(workflow_json)

            return ArchitectureResult(
                success     = True,
                mermaid     = mermaid,
                ascii_art   = ascii_art,
                description = description,
                components  = components,
                data_flows  = data_flows,
            )
        except Exception as exc:
            return ArchitectureResult(success=False, error=str(exc))

    # ------------------------------------------------------------------
    # Mermaid flowchart
    # ------------------------------------------------------------------

    def _generate_mermaid(self, wf: Dict) -> str:
        """Generate a Mermaid LR flowchart diagram."""
        lines: List[str] = []
        lines.append("flowchart LR")
        lines.append("")

        # Style classes
        for node_type, style in _MERMAID_STYLES.items():
            lines.append(f"    classDef {node_type}Style {style}")
        lines.append("")

        # Trigger node
        triggers = wf.get("triggers", [])
        if triggers:
            for t in triggers:
                tid   = self._safe_id(t.get("id", "trigger"))
                ttype = t.get("type", "trigger")
                icon  = self._trigger_icon(ttype)
                lines.append(f'    {tid}(["{icon} {ttype.title()} Trigger"])')
            lines.append("")

        # Workflow nodes
        style_assignments: List[str] = []
        nodes      = wf.get("nodes", [])
        node_map   = {n.get("id"): n for n in nodes}

        for node in nodes:
            nid        = self._safe_id(node.get("id", "node"))
            name       = self._escape_mermaid(node.get("name", nid))
            node_type  = node.get("type", "action")
            icon       = self._node_icon(node_type)
            open_s, close_s = _MERMAID_SHAPES.get(node_type, ("[", "]"))

            # Add indicators
            indicators = []
            if node.get("retry"):    indicators.append("↻")
            if node.get("timeout"):  indicators.append("⏱")
            label = f"{icon} {name}"
            if indicators:
                label += f" {''.join(indicators)}"

            lines.append(f'    {nid}{open_s}"{label}"{close_s}')
            style_assignments.append(f"    class {nid} {node_type}Style")

        lines.append("")

        # Connections — from triggers to first nodes
        first_nodes = [n for n in nodes if not n.get("depends_on")]
        for trigger in triggers:
            tid = self._safe_id(trigger.get("id", "trigger"))
            for first in first_nodes:
                fid = self._safe_id(first.get("id", ""))
                lines.append(f"    {tid} --> {fid}")

        # Node edges
        for node in nodes:
            nid      = self._safe_id(node.get("id", ""))
            for dep in node.get("depends_on", []):
                did = self._safe_id(dep)
                # Label condition branches
                dep_node = node_map.get(dep)
                if dep_node and dep_node.get("type") == "condition":
                    label = "yes" if nodes.index(node) % 2 == 0 else "no"
                    lines.append(f"    {did} -->|{label}| {nid}")
                else:
                    lines.append(f"    {did} --> {nid}")

        lines.append("")
        lines.extend(style_assignments)
        lines.append("")

        # Subgraphs for parallel blocks
        for node in nodes:
            if node.get("type") == "parallel":
                nid     = self._safe_id(node.get("id", ""))
                branches = node.get("parallel", {}).get("branches", [])
                lines.append(f"    subgraph {nid}_parallel [Parallel: {node.get('name', '')}]")
                for bi, branch in enumerate(branches):
                    bname = branch.get("name", f"Branch {bi+1}")
                    lines.append(f"        subgraph branch_{nid}_{bi} [{bname}]")
                    for sub in branch.get("nodes", []):
                        sid   = self._safe_id(sub.get("id", f"sub_{bi}"))
                        sname = self._escape_mermaid(sub.get("name", sid))
                        lines.append(f"            {sid}[\"{sname}\"]")
                    lines.append("        end")
                lines.append("    end")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # ASCII art
    # ------------------------------------------------------------------

    def _generate_ascii(self, wf: Dict) -> str:
        """Generate a simple ASCII box diagram."""
        nodes   = wf.get("nodes", [])
        name    = wf.get("name", "Workflow")
        lines   = []
        width   = 60

        # Header
        lines.append("┌" + "─" * (width - 2) + "┐")
        title   = f" {name} "
        padding = (width - 2 - len(title)) // 2
        lines.append("│" + " " * padding + title + " " * (width - 2 - padding - len(title)) + "│")
        lines.append("└" + "─" * (width - 2) + "┘")
        lines.append("")

        # Trigger
        triggers = wf.get("triggers", [])
        if triggers:
            t = triggers[0]
            t_label = f"⚡ TRIGGER: {t.get('type', '').upper()}"
            lines.append("  ┌─────────────────────────────────────────────┐")
            lines.append(f"  │  {t_label:<43}│")
            lines.append("  └───────────────────────┬─────────────────────┘")
            lines.append("                          │")

        # Topological sort
        sorted_nodes = self._topo_sort(nodes)

        for i, node in enumerate(sorted_nodes):
            node_type = node.get("type", "action")
            name_s    = node.get("name", node.get("id", ""))[:38]
            icon      = self._node_icon(node_type)
            type_tag  = f"[{node_type.upper()[:10]}]"
            extras    = ""
            if node.get("retry"):   extras += " ↻"
            if node.get("timeout"): extras += " ⏱"

            label = f"{icon}  {name_s}{extras}"
            lines.append(f"  ┌─────────────────────────────────────────────┐")
            lines.append(f"  │  {label:<43}│")
            lines.append(f"  │  {type_tag:<43}│")

            # Show depends_on
            deps = node.get("depends_on", [])
            if deps:
                dep_str = f"  ← depends on: {', '.join(deps[:2])}"
                if len(deps) > 2:
                    dep_str += f" +{len(deps)-2}"
                lines.append(f"  │  {dep_str:<43}│")

            lines.append(f"  └───────────────────────┬─────────────────────┘")
            if i < len(sorted_nodes) - 1:
                lines.append("                          │")
                if sorted_nodes[i + 1].get("type") == "condition":
                    lines.append("                         ╔╩╗")
                    lines.append("                         ║?║  (condition)")
                    lines.append("                         ╚╦╝")
                else:
                    lines.append("                          ▼")
        lines.append("")
        lines.append(f"  Total nodes: {len(nodes)}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Description
    # ------------------------------------------------------------------

    def _generate_description(self, wf: Dict) -> str:
        """AI-generated architecture description."""
        compact = {
            "name":        wf.get("name"),
            "description": wf.get("description"),
            "triggers":    [{"type": t.get("type")} for t in wf.get("triggers", [])],
            "nodes": [{
                "id":   n.get("id"),
                "name": n.get("name"),
                "type": n.get("type"),
                "depends_on": n.get("depends_on", []),
            } for n in wf.get("nodes", [])],
        }
        messages = [
            {"role": "system", "content": "You are a technical writer. Describe the architecture of this workflow in 3–4 short paragraphs. Use headings: Overview, Data Flow, Error Handling, Integrations."},
            {"role": "user",   "content": f"Architecture description for:\n{json.dumps(compact, indent=2)}"},
        ]
        try:
            return self._ai.chat(messages, max_tokens=500).strip()
        except Exception:
            nodes = wf.get("nodes", [])
            types = list({n.get("type", "action") for n in nodes})
            return (
                f"## {wf.get('name', 'Workflow')}\n\n"
                f"**Overview**: {wf.get('description', 'A multi-step automated workflow.')}\n\n"
                f"**Nodes**: {len(nodes)} nodes using types: {', '.join(types)}.\n\n"
                f"**Trigger**: {wf.get('triggers', [{}])[0].get('type', 'manual')} trigger."
            )

    # ------------------------------------------------------------------
    # Components & data flows
    # ------------------------------------------------------------------

    def _extract_components(self, wf: Dict) -> List[Dict]:
        components = []
        for node in wf.get("nodes", []):
            comp = {
                "id":        node.get("id"),
                "name":      node.get("name"),
                "type":      node.get("type"),
                "icon":      self._node_icon(node.get("type", "action")),
                "has_retry": bool(node.get("retry")),
                "has_timeout": bool(node.get("timeout")),
                "depends_on": node.get("depends_on", []),
            }
            # Extract integration
            if node.get("type") == "action":
                comp["integration"] = node.get("action", {}).get("integration", "")
                comp["operation"]   = node.get("action", {}).get("operation", "")
            elif node.get("type") == "ai":
                comp["model"] = node.get("ai", {}).get("model", "")
            elif node.get("type") == "notification":
                comp["channels"] = [t.get("channel") for t in node.get("notification", {}).get("targets", [])]
            components.append(comp)
        return components

    def _extract_data_flows(self, wf: Dict) -> List[Dict]:
        flows = []
        node_map = {n.get("id"): n for n in wf.get("nodes", [])}
        for node in wf.get("nodes", []):
            for dep in node.get("depends_on", []):
                dep_node = node_map.get(dep, {})
                flows.append({
                    "from":      dep,
                    "to":        node.get("id"),
                    "from_type": dep_node.get("type", "unknown"),
                    "to_type":   node.get("type", "unknown"),
                    "label":     f"{dep_node.get('name', dep)} → {node.get('name', node.get('id'))}",
                })
        return flows

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _safe_id(node_id: str) -> str:
        """Convert node_id to a Mermaid-safe identifier."""
        return re.sub(r"[^a-zA-Z0-9_]", "_", str(node_id))

    @staticmethod
    def _escape_mermaid(text: str) -> str:
        return str(text).replace('"', "'").replace("[", "(").replace("]", ")")

    @staticmethod
    def _node_icon(node_type: str) -> str:
        return {
            "action":         "⚡",
            "condition":      "🔀",
            "ai":             "🤖",
            "notification":   "🔔",
            "webhook":        "🌐",
            "parallel":       "⫸",
            "loop":           "🔄",
            "human_approval": "👤",
            "delay":          "⏳",
            "transform":      "🔧",
            "subworkflow":    "📦",
        }.get(node_type, "▪")

    @staticmethod
    def _trigger_icon(trigger_type: str) -> str:
        return {
            "cron":    "🕐",
            "webhook": "📥",
            "manual":  "👆",
            "event":   "📡",
            "form":    "📝",
        }.get(trigger_type, "⚡")

    @staticmethod
    def _topo_sort(nodes: List[Dict]) -> List[Dict]:
        """Return nodes in topological order (no circular dependency handling)."""
        node_map = {n.get("id"): n for n in nodes}
        visited: set = set()
        result: List[Dict] = []

        def visit(nid: str) -> None:
            if nid in visited:
                return
            visited.add(nid)
            node = node_map.get(nid)
            if node:
                for dep in node.get("depends_on", []):
                    visit(dep)
                result.append(node)

        for node in nodes:
            visit(node.get("id", ""))

        return result
