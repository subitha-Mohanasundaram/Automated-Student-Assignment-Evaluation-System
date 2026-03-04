from __future__ import annotations

import pytest


def _get_target(student_module):
    if not hasattr(student_module, "solve"):
        pytest.fail("Student file must define function: solve(input_str)")
    return getattr(student_module, "solve")


def test_two_sum_visible_1(student_module) -> None:
    fn = _get_target(student_module)
    assert fn("2 7 11 15|9") == "0 1"


def test_two_sum_visible_2(student_module) -> None:
    fn = _get_target(student_module)
    assert fn("3 2 4|6") == "1 2"
