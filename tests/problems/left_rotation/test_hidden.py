from __future__ import annotations

import pytest


def _get_target(student_module):
    if not hasattr(student_module, "solve"):
        pytest.fail("Student file must define function: solve(input_str)")
    return getattr(student_module, "solve")


def test_left_rotation_hidden_1(student_module) -> None:
    fn = _get_target(student_module)
    assert fn("1 2 3|0") == "1 2 3"


def test_left_rotation_hidden_2(student_module) -> None:
    fn = _get_target(student_module)
    assert fn("7 8 9 10|5") == "8 9 10 7"
