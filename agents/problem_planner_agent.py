from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agents.messages import AgentMessage


@dataclass(frozen=True)
class ProblemPlan:
    tool_calls: list[dict[str, Any]]


class ProblemPlannerAgent:
    """Plans the AI problem generation tool sequence."""

    def plan(self, *, title: str, problem_description: str) -> AgentMessage:
        tool_calls: list[dict[str, Any]] = [
            {"id": "meta", "name": "generate_problem_metadata", "arguments": {"title": title, "problem_description": problem_description}},
            {
                "id": "ref",
                "name": "generate_reference_solution",
                "arguments": {
                    "title": title,
                    "problem_description": problem_description,
                    "constraints": "${meta.details.constraints}",
                    "examples": "${meta.details.examples}",
                },
            },
            {
                "id": "tc",
                "name": "generate_test_cases",
                "arguments": {
                    "title": title,
                    "problem_description": problem_description,
                    "constraints": "${meta.details.constraints}",
                    "difficulty": "${meta.details.difficulty}",
                    "visible_count": 3,
                    "hidden_count": 10,
                    "stress_count": 20,
                },
            },
            {"id": "exp_vis", "name": "compute_expected_outputs", "arguments": {"reference_solution_code": "${ref.details.code}", "inputs": "${tc.details.visible_inputs}"}},
            {"id": "exp_hid", "name": "compute_expected_outputs", "arguments": {"reference_solution_code": "${ref.details.code}", "inputs": "${tc.details.hidden_inputs}"}},
            {"id": "exp_str", "name": "compute_expected_outputs", "arguments": {"reference_solution_code": "${ref.details.code}", "inputs": "${tc.details.stress_inputs}"}},
        ]
        return AgentMessage(role="planner", type="problem_generation_plan", payload={"tool_calls": tool_calls})

