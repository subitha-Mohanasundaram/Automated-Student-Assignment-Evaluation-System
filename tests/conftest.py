"""Pytest configuration for loading a submitted student module."""

from __future__ import annotations

import importlib.util
import shutil
import uuid
from pathlib import Path

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--student-file",
        action="store",
        default=None,
        help="Path to the student's Python file",
    )


@pytest.fixture(scope="session")
def student_module(request: pytest.FixtureRequest):
    student_file_arg = request.config.getoption("--student-file")
    if not student_file_arg:
        pytest.skip("No --student-file provided; skipping submission tests.")

    student_path = Path(student_file_arg).resolve()
    if not student_path.exists():
        pytest.fail(f"Student file not found: {student_path}")

    spec = importlib.util.spec_from_file_location("student_submission", student_path)
    if spec is None or spec.loader is None:
        pytest.fail(f"Unable to load student module from: {student_path}")

    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        pytest.fail(f"Error while importing student file: {exc}")

    return module


@pytest.fixture
def tmp_path() -> Path:
    # Windows in this environment blocks pytest's default temp dirs (names like "pytest-*")
    # and also blocks the user temp directory, so we provide a workspace-local alternative.
    root = Path("sandbox_tmp") / "tmp_test_dirs"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"tmp_{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)
