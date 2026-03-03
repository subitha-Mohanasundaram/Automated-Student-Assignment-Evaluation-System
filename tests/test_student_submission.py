"""Predefined test cases for student submissions.

Expected student submission interface:
- A function named add_numbers(a, b) that returns the sum of two numbers.
"""

from __future__ import annotations

import pytest


def _get_add_numbers(student_module):
    if not hasattr(student_module, "add_numbers"):
        pytest.fail("Student file must define a function: add_numbers(a, b)")
    return getattr(student_module, "add_numbers")


def test_add_positive_numbers(student_module) -> None:
    add_numbers = _get_add_numbers(student_module)
    assert add_numbers(2, 3) == 5


def test_add_negative_numbers(student_module) -> None:
    add_numbers = _get_add_numbers(student_module)
    assert add_numbers(-2, -7) == -9


def test_add_mixed_numbers(student_module) -> None:
    add_numbers = _get_add_numbers(student_module)
    assert add_numbers(-2, 10) == 8


def test_add_with_zero(student_module) -> None:
    add_numbers = _get_add_numbers(student_module)
    assert add_numbers(0, 99) == 99
