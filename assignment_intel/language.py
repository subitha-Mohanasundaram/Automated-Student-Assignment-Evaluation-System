from __future__ import annotations

from pathlib import Path


def detect_language(*, filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext == ".py":
        return "python"
    if ext == ".java":
        return "java"
    if ext in {".cpp", ".cc", ".cxx"}:
        return "cpp"
    if ext == ".c":
        return "c"
    if ext == ".js":
        return "javascript"
    return "python"

