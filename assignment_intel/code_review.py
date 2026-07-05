from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ReviewFinding:
    level: str  # info|warning
    message: str


def review_python_file(path: Path) -> list[ReviewFinding]:
    findings: list[ReviewFinding] = []
    try:
        source = path.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")
        tree = ast.parse(source, filename=str(path))
    except (OSError, SyntaxError) as exc:
        return [ReviewFinding(level="warning", message=f"Could not parse Python file: {exc}")]

    func_defs = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
    if not func_defs:
        findings.append(ReviewFinding(level="warning", message="No functions found; ensure you implemented the required function."))

    has_print = any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "print" for n in ast.walk(tree))
    if has_print:
        findings.append(ReviewFinding(level="info", message="Uses print(); avoid debug prints unless required by the problem."))

    return findings

