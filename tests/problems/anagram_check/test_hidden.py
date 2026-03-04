from __future__ import annotations

import pytest


def _get_target(student_module):
    if not hasattr(student_module, "solve"):
        pytest.fail("Student file must define function: solve(input_str)")
    return getattr(student_module, "solve")


def test_anagram_hidden_1(student_module) -> None:
    fn = _get_target(student_module)
    assert fn("evil|vile") == "true"


def test_anagram_hidden_2(student_module) -> None:
    fn = _get_target(student_module)
    assert fn("aabb|ab") == "false"
