from pathlib import Path

from evaluator import _compute_fingerprint, _detect_plagiarism


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_detects_exact_fingerprint_match_for_python(tmp_path: Path) -> None:
    repo = tmp_path
    alice = repo / "submissions" / "alice" / "student_solution.py"
    bob = repo / "submissions" / "bob" / "student_solution.py"

    src = "def add_numbers(a, b):\n    return a + b\n"
    _write(alice, src)
    _write(bob, src)

    bob_fp = _compute_fingerprint(bob, "python")
    detected, matches, risk, evidence = _detect_plagiarism(
        repo_root=repo,
        student_file=bob,
        language="python",
        problem_id="add_numbers",
        current_username="bob",
        current_fingerprint=bob_fp,
    )

    assert detected is True
    assert risk == 100.0
    assert any("alice" in item for item in matches)
    assert any("fingerprint" in item.lower() for item in evidence)


def test_does_not_flag_distinct_python_submission(tmp_path: Path) -> None:
    repo = tmp_path
    alice = repo / "submissions" / "alice" / "student_solution.py"
    bob = repo / "submissions" / "bob" / "student_solution.py"

    _write(alice, "def add_numbers(a, b):\n    return a + b\n")
    _write(
        bob,
        (
            "def add_numbers(a, b):\n"
            "    total = 0\n"
            "    for value in (a, b):\n"
            "        total += value\n"
            "    return total\n"
        ),
    )

    bob_fp = _compute_fingerprint(bob, "python")
    detected, matches, risk, _ = _detect_plagiarism(
        repo_root=repo,
        student_file=bob,
        language="python",
        problem_id="add_numbers",
        current_username="bob",
        current_fingerprint=bob_fp,
    )

    assert detected is False
    assert matches == []
    assert risk < 90.0
