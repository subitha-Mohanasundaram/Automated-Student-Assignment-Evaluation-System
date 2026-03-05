from pathlib import Path

import pytest

from workflow_helpers import resolve_student_details, write_unmapped_csv


def test_resolve_student_details_mapped_user(tmp_path: Path) -> None:
    students = tmp_path / "students.csv"
    students.write_text(
        "github_username,student_name,email\nalice,Alice,alice@example.com\n",
        encoding="utf-8",
    )

    result = resolve_student_details(students_file=students, actor="alice", admin_email="admin@example.com")

    assert result.mapped is True
    assert result.name == "Alice"
    assert result.email == "alice@example.com"


def test_resolve_student_details_uses_admin_fallback(tmp_path: Path) -> None:
    students = tmp_path / "students.csv"
    students.write_text("github_username,student_name,email\n", encoding="utf-8")

    result = resolve_student_details(students_file=students, actor="unknown", admin_email="admin@example.com")

    assert result.mapped is False
    assert result.name == "unknown"
    assert result.email == "admin@example.com"


def test_resolve_student_details_raises_without_email(tmp_path: Path) -> None:
    students = tmp_path / "students.csv"
    students.write_text("github_username,student_name,email\nbob,Bob,\n", encoding="utf-8")

    with pytest.raises(ValueError):
        resolve_student_details(students_file=students, actor="bob", admin_email="admin@example.com")


def test_write_unmapped_csv(tmp_path: Path) -> None:
    students = tmp_path / "students.csv"
    students.write_text("github_username,student_name,email\n", encoding="utf-8")
    result = resolve_student_details(students_file=students, actor="ghost", admin_email="admin@example.com")

    out = tmp_path / "unmapped.csv"
    write_unmapped_csv(
        output_file=out,
        resolution=result,
        workflow_run_id="123",
        workflow_url="https://example.com/run/123",
    )

    content = out.read_text(encoding="utf-8")
    assert "github_username,detected_at_utc,workflow_run_id,workflow_url" in content
    assert "ghost" in content
    assert "123" in content
