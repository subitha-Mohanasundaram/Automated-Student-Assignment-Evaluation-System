from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


def safe_slug(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = value.strip("_")
    return value or "student"


@dataclass(frozen=True)
class StoredSubmission:
    path: Path
    username: str
    problem_id: str
    language: str
    saved_at: datetime


def save_submission_bytes(*, student_name: str, problem_id: str, filename: str, content: bytes) -> StoredSubmission:
    username = safe_slug(student_name)
    problem_slug = safe_slug(problem_id)

    suffix = Path(filename).suffix.lower()
    if suffix not in {".py", ".java", ".cpp", ".cc", ".cxx", ".c", ".js"}:
        raise ValueError("Unsupported file type; use .py, .java, .c, .cpp, or .js")

    language = {
        ".py": "python",
        ".java": "java",
        ".c": "c",
        ".cpp": "cpp",
        ".cc": "cpp",
        ".cxx": "cpp",
        ".js": "javascript",
    }[suffix]
    saved_at = datetime.utcnow()
    out_dir = Path("submissions") / username / problem_slug
    out_dir.mkdir(parents=True, exist_ok=True)

    # Normalize extensions on disk for easier downstream tooling.
    normalized_suffix = ".cpp" if suffix in {".cc", ".cxx"} else suffix
    out_path = out_dir / f"submission{normalized_suffix}"
    # Strip common BOMs that can break parsing in downstream tooling.
    if content.startswith(b"\xef\xbb\xbf"):  # UTF-8 BOM
        content = content[3:]
    elif content.startswith(b"\xff\xfe"):  # UTF-16 LE BOM
        content = content[2:]
    elif content.startswith(b"\xfe\xff"):  # UTF-16 BE BOM
        content = content[2:]
    out_path.write_bytes(content)

    return StoredSubmission(path=out_path.resolve(), username=username, problem_id=problem_slug, language=language, saved_at=saved_at)


def save_submission_text(*, student_name: str, problem_id: str, language: str, code: str, versioned: bool = True) -> StoredSubmission:
    """Save a submission from an in-browser editor.

    If versioned=True, stores a timestamped copy and also updates the canonical submission.<ext>.
    """
    lang = (language or "").strip().lower()
    ext = {"python": ".py", "java": ".java", "c": ".c", "cpp": ".cpp", "javascript": ".js"}.get(lang)
    if not ext:
        raise ValueError("Unsupported language for editor submission.")

    username = safe_slug(student_name)
    problem_slug = safe_slug(problem_id)
    saved_at = datetime.utcnow()
    out_dir = Path("submissions") / username / problem_slug
    out_dir.mkdir(parents=True, exist_ok=True)

    canonical = out_dir / f"submission{ext}"
    content = code.encode("utf-8")
    if content.startswith(b"\xef\xbb\xbf"):
        content = content[3:]

    canonical.write_bytes(content)
    if not versioned:
        return StoredSubmission(path=canonical.resolve(), username=username, problem_id=problem_slug, language=lang, saved_at=saved_at)

    ts = saved_at.strftime("%Y%m%d_%H%M%S")
    versioned_path = out_dir / f"submission_{ts}{ext}"
    versioned_path.write_bytes(content)
    return StoredSubmission(path=versioned_path.resolve(), username=username, problem_id=problem_slug, language=lang, saved_at=saved_at)
