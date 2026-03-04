"""Visible tests for problem: left_rotation."""

from __future__ import annotations

import pytest


def _get_target(student_module):
    if not hasattr(student_module, "solve"):
        pytest.fail("Student file must define function: solve(a, b)")
    return getattr(student_module, "solve")


def test_visible_case_1(student_module) -> None:
    fn = _get_target(student_module)
    assert fn(1, 2) == 3


def test_visible_case_2(student_module) -> None:
    fn = _get_target(student_module)
    assert fn(4, 5) == 9
