from __future__ import annotations

import os
from typing import Any

# Load environment variables from .env so MCP tools can access AI credentials.
try:  # pragma: no cover
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

from fastmcp import FastMCP

from observability.logger import log_tool_call

from platform_mcp.tools_execution import compile_code as _compile_code
from platform_mcp.tools_execution import run_code as _run_code
from platform_mcp.tools_tests import evaluate_tests as _evaluate_tests
from platform_mcp.tools_plagiarism import detect_plagiarism as _detect_plagiarism
from platform_mcp.tools_analysis import analyze_complexity as _analyze_complexity
from platform_mcp.tools_analysis import code_quality_analysis as _code_quality_analysis
from platform_mcp.tools_feedback import generate_feedback as _generate_feedback
from platform_mcp.tools_test_expansion import generate_hidden_test_expansion as _generate_hidden_test_expansion
from platform_mcp.tools_problem_gen import (
    compute_expected_outputs as _compute_expected_outputs,
    generate_problem_metadata as _generate_problem_metadata,
    generate_reference_solution as _generate_reference_solution,
    generate_test_cases as _generate_test_cases,
)


def _get_host_port() -> tuple[str, int]:
    host = os.getenv("MCP_HOST", "127.0.0.1").strip()
    port_raw = os.getenv("MCP_PORT", "8000").strip()
    try:
        port = int(port_raw)
    except ValueError:
        port = 8000
    return host, port


def create_server() -> FastMCP:
    mcp = FastMCP("assignment-intel")

    @mcp.tool()
    def run_code(language: str, submission_path: str, stdin: str = "", timeout_s: int = 10) -> dict[str, Any]:
        res = _run_code(language=language, submission_path=submission_path, stdin=stdin, timeout_s=timeout_s)
        log_tool_call(tool="run_code", arguments={"language": language, "submission_path": submission_path}, result=res, source="mcp:sse")
        return res

    @mcp.tool()
    def compile_code(language: str, submission_path: str) -> dict[str, Any]:
        res = _compile_code(language=language, submission_path=submission_path)
        log_tool_call(tool="compile_code", arguments={"language": language, "submission_path": submission_path}, result=res, source="mcp:sse")
        return res

    @mcp.tool()
    def evaluate_tests(
        student_name: str,
        problem_id: str,
        language: str,
        submission_path: str,
        extra_hidden_cases_path: str | None = None,
    ) -> dict[str, Any]:
        res = _evaluate_tests(
            student_name=student_name,
            problem_id=problem_id,
            language=language,
            submission_path=submission_path,
            extra_hidden_cases_path=extra_hidden_cases_path,
        )
        log_tool_call(
            tool="evaluate_tests",
            arguments={"student_name": student_name, "problem_id": problem_id, "language": language, "submission_path": submission_path},
            result=res,
            source="mcp:sse",
        )
        return res

    @mcp.tool()
    def detect_plagiarism(submission_path: str, corpus_dir: str = "submissions", threshold: float = 0.8) -> dict[str, Any]:
        res = _detect_plagiarism(submission_path=submission_path, corpus_dir=corpus_dir, threshold=threshold)
        log_tool_call(
            tool="detect_plagiarism",
            arguments={"submission_path": submission_path, "corpus_dir": corpus_dir, "threshold": threshold},
            result=res,
            source="mcp:sse",
        )
        return res

    @mcp.tool()
    def analyze_complexity(language: str, submission_path: str) -> dict[str, Any]:
        res = _analyze_complexity(language=language, submission_path=submission_path)
        log_tool_call(tool="analyze_complexity", arguments={"language": language, "submission_path": submission_path}, result=res, source="mcp:sse")
        return res

    @mcp.tool()
    def code_quality_analysis(language: str, submission_path: str) -> dict[str, Any]:
        res = _code_quality_analysis(language=language, submission_path=submission_path)
        log_tool_call(tool="code_quality_analysis", arguments={"language": language, "submission_path": submission_path}, result=res, source="mcp:sse")
        return res

    @mcp.tool()
    def generate_feedback(
        student_name: str,
        problem_id: str,
        language: str,
        submission_path: str,
        eval_results: dict | None = None,
    ) -> dict[str, Any]:
        res = _generate_feedback(
            student_name=student_name,
            problem_id=problem_id,
            language=language,
            submission_path=submission_path,
            eval_results=eval_results or {},
        )
        log_tool_call(tool="generate_feedback", arguments={"student_name": student_name, "problem_id": problem_id}, result=res, source="mcp:sse")
        return res

    @mcp.tool()
    def generate_hidden_test_expansion(problem_id: str, count: int = 10) -> dict[str, Any]:
        res = _generate_hidden_test_expansion(problem_id=problem_id, count=count)
        log_tool_call(tool="generate_hidden_test_expansion", arguments={"problem_id": problem_id, "count": count}, result=res, source="mcp:sse")
        return res

    @mcp.tool()
    def generate_problem_metadata(title: str, problem_description: str) -> dict[str, Any]:
        res = _generate_problem_metadata(title=title, problem_description=problem_description)
        log_tool_call(tool="generate_problem_metadata", arguments={"title": title}, result=res, source="mcp:sse")
        return res

    @mcp.tool()
    def generate_reference_solution(title: str, problem_description: str, constraints: str = "", examples: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        res = _generate_reference_solution(title=title, problem_description=problem_description, constraints=constraints, examples=examples or [])
        log_tool_call(tool="generate_reference_solution", arguments={"title": title}, result=res, source="mcp:sse")
        return res

    @mcp.tool()
    def generate_test_cases(
        title: str,
        problem_description: str,
        constraints: str = "",
        difficulty: str = "medium",
        visible_count: int = 3,
        hidden_count: int = 10,
        stress_count: int = 20,
    ) -> dict[str, Any]:
        res = _generate_test_cases(
            title=title,
            problem_description=problem_description,
            constraints=constraints,
            difficulty=difficulty,
            visible_count=visible_count,
            hidden_count=hidden_count,
            stress_count=stress_count,
        )
        log_tool_call(tool="generate_test_cases", arguments={"title": title}, result=res, source="mcp:sse")
        return res

    @mcp.tool()
    def compute_expected_outputs(reference_solution_code: str, inputs: list[str], timeout_s: int = 8) -> dict[str, Any]:
        res = _compute_expected_outputs(reference_solution_code=reference_solution_code, inputs=inputs, timeout_s=timeout_s)
        log_tool_call(tool="compute_expected_outputs", arguments={"inputs_count": len(inputs)}, result=res, source="mcp:sse")
        return res

    return mcp


def main() -> None:
    host, port = _get_host_port()
    create_server().run(transport="sse", host=host, port=port)


if __name__ == "__main__":
    main()
