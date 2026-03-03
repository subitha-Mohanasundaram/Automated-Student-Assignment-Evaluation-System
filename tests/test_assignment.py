"""Sample pytest suite for the assignment: implement add(a, b)."""

from __future__ import annotations

import pytest


def _get_add(student_module):
    if not hasattr(student_module, "add"):
        pytest.fail("Student file must define a function: add(a, b)")
    return getattr(student_module, "add")


def test_add_positive_numbers(student_module) -> None:
    add = _get_add(student_module)
    assert add(2, 3) == 5


def test_add_negative_numbers(student_module) -> None:
    add = _get_add(student_module)
    assert add(-4, -6) == -10


def test_add_mixed_sign_numbers(student_module) -> None:
    add = _get_add(student_module)
    assert add(-2, 7) == 5


def test_add_with_zero(student_module) -> None:
    add = _get_add(student_module)
    assert add(0, 11) == 11


def test_add_large_numbers(student_module) -> None:
    add = _get_add(student_module)
    assert add(1_000_000, 2_000_000) == 3_000_000


def test_add_float_numbers(student_module) -> None:
    add = _get_add(student_module)
    assert add(2.5, 0.5) == 3.0
