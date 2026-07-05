from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ComplexityEstimate:
    time_complexity: str
    space_complexity: str
    notes: list[str]


class _LoopDepth(ast.NodeVisitor):
    def __init__(self) -> None:
        self.max_depth = 0
        self._depth = 0
        self.has_recursion = False
        self._current_func: str | None = None

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        prev = self._current_func
        self._current_func = node.name
        self.generic_visit(node)
        self._current_func = prev

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        prev = self._current_func
        self._current_func = node.name
        self.generic_visit(node)
        self._current_func = prev

    def visit_For(self, node: ast.For) -> None:
        self._depth += 1
        self.max_depth = max(self.max_depth, self._depth)
        self.generic_visit(node)
        self._depth -= 1

    def visit_While(self, node: ast.While) -> None:
        self._depth += 1
        self.max_depth = max(self.max_depth, self._depth)
        self.generic_visit(node)
        self._depth -= 1

    def visit_Call(self, node: ast.Call) -> None:
        if self._current_func and isinstance(node.func, ast.Name) and node.func.id == self._current_func:
            self.has_recursion = True
        self.generic_visit(node)


def estimate_python_complexity(source_file: Path) -> ComplexityEstimate:
    source = source_file.read_text(encoding="utf-8", errors="replace")
    source = source.lstrip("\ufeff")
    tree = ast.parse(source)

    visitor = _LoopDepth()
    visitor.visit(tree)

    notes: list[str] = []
    if visitor.max_depth <= 0:
        time_complexity = "O(1) to O(n)"
        notes.append("No explicit loops detected; complexity depends on library calls.")
    elif visitor.max_depth == 1:
        time_complexity = "O(n)"
    else:
        time_complexity = f"O(n^{visitor.max_depth})"
        notes.append("Nested loops detected; consider optimizing with hashing or sorting.")

    if visitor.has_recursion:
        notes.append("Recursion detected; verify base cases and consider iterative solutions.")

    # Heuristic: if recursion or loops present, space may be O(n) due to call stack / data structures.
    space_complexity = "O(n)" if visitor.has_recursion else "O(1) to O(n)"
    return ComplexityEstimate(time_complexity=time_complexity, space_complexity=space_complexity, notes=notes)
