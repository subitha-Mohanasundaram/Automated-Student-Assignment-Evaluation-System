"""Hidden test cases for student submissions.

These tests are executed by the evaluator but should not be shown to candidates
in an interview setting. Move this file to a private grading repository when
using this in production.
"""

from __future__ import annotations

import pytest


def _get_add_numbers(student_module):
    if not hasattr(student_module, "add_numbers"):
        pytest.fail("Student file must define a function: add_numbers(a, b)")
    return getattr(student_module, "add_numbers")


def test_add_large_numbers(student_module) -> None:
    add_numbers = _get_add_numbers(student_module)
    assert add_numbers(10_000_000, 23_000_000) == 33_000_000


def test_add_float_numbers(student_module) -> None:
    add_numbers = _get_add_numbers(student_module)
    assert add_numbers(0.1, 0.2) == pytest.approx(0.3)


def test_add_negative_and_float(student_module) -> None:
    add_numbers = _get_add_numbers(student_module)
    assert add_numbers(-2.5, 1.5) == pytest.approx(-1.0)
