from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from assignment_intel.sandbox_runner import get_docker_image_for_language, run_in_docker


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def run_code(*, language: str, submission_path: str, stdin: str = "", timeout_s: int = 10) -> dict[str, Any]:
    path = Path(submission_path).resolve()
    if not path.exists():
        return {"success": False, "error": "file_not_found", "details": {"path": str(path)}}

    lang = language.strip().lower()
    repo_root = _repo_root()

    # Enforce Docker sandbox for code execution.
    try:
        rel = path.relative_to(repo_root)
    except Exception as exc:
        return {"success": False, "error": "path_error", "details": {"message": str(exc)}}
    image = get_docker_image_for_language(lang)
    relp = str(rel).replace("\\", "/")
    # For compiled languages, run_code performs compile+run (smoke).
    if lang == "python":
        cmd = ["python", relp]
    elif lang == "javascript":
        cmd = ["node", relp]
    elif lang == "java":
        cmd = ["bash", "-lc", f"cd /workspace && javac {relp} && java -cp $(dirname {relp}) $(basename {relp} .java)"]
    elif lang == "c":
        cmd = ["bash", "-lc", f"cd /workspace && gcc -O2 -std=c11 {relp} -o /tmp/a.out && /tmp/a.out"]
    elif lang == "cpp":
        cmd = ["bash", "-lc", f"cd /workspace && g++ -O2 -std=c++17 {relp} -o /tmp/a.out && /tmp/a.out"]
    else:
        return {"success": False, "error": "unsupported_language", "details": {"language": lang}}
    res = run_in_docker(repo_root=repo_root, image=image, command=cmd, timeout_s=timeout_s, cpus="1", memory="512m")
    if res.error == "docker_not_available":
        return {"success": False, "error": "docker_required", "details": {"message": "Docker is required for run_code. Start Docker Desktop and retry."}}
    return {"success": res.ok, "exit_code": res.exit_code, "stdout": res.stdout, "stderr": res.stderr, "details": {"sandbox": "docker"}}


def compile_code(*, language: str, submission_path: str) -> dict[str, Any]:
    path = Path(submission_path).resolve()
    if not path.exists():
        return {"success": False, "error": "file_not_found", "details": {"path": str(path)}}
    lang = language.strip().lower()
    repo_root = _repo_root()

    if lang not in {"java", "cpp", "c"}:
        return {"success": False, "error": "unsupported_language", "details": {"language": lang}}

    # Enforce Docker sandbox for compilation.
    try:
        rel = path.relative_to(repo_root)
    except Exception as exc:
        return {"success": False, "error": "path_error", "details": {"message": str(exc)}}
    image = get_docker_image_for_language(lang)
    if lang == "java":
        cmd = ["javac", str(rel).replace("\\", "/")]
    elif lang == "c":
        cmd = ["bash", "-lc", f"cd /workspace && gcc -std=c11 -O2 {str(rel).replace('\\\\','/')} -o /tmp/a.out"]
    else:
        cmd = ["bash", "-lc", f"cd /workspace && g++ -std=c++17 -O2 {str(rel).replace('\\\\','/')} -o /tmp/a.out"]
    res = run_in_docker(repo_root=repo_root, image=image, command=cmd, timeout_s=60, cpus="1", memory="512m")
    if res.error == "docker_not_available":
        return {"success": False, "error": "docker_required", "details": {"message": "Docker is required for compile_code. Start Docker Desktop and retry."}}
    return {"success": res.ok, "exit_code": res.exit_code, "stdout": res.stdout, "stderr": res.stderr, "details": {"sandbox": "docker"}}
