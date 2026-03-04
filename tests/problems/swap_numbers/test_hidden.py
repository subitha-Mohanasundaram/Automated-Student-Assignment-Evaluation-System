"""Hidden tests for problem: swap_numbers."""

from __future__ import annotations

import pytest


def _get_target(student_module):
    if not hasattr(student_module, "solve"):
        pytest.fail("Student file must define function: solve(a, b)")
    return getattr(student_module, "solve")


def test_hidden_case_1(student_module) -> None:
    fn = _get_target(student_module)
    assert fn(-3, 7) == 4


def test_hidden_case_2(student_module) -> None:
    fn = _get_target(student_module)
    assert fn(0, 0) == 0
