from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from assignment_intel.models import ToolResult


ToolFn = Callable[..., ToolResult]


@dataclass(frozen=True)
class Tool:
    name: str
    fn: ToolFn


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool already registered: {tool.name}")
        self._tools[tool.name] = tool

    def call(self, name: str, **kwargs: Any) -> ToolResult:
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(tool=name, ok=False, error="unknown_tool")
        return tool.fn(**kwargs)

    def names(self) -> list[str]:
        return sorted(self._tools.keys())

