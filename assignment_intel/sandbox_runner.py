from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SandboxResult:
    ok: bool
    exit_code: int
    stdout: str
    stderr: str
    error: str | None = None


def _docker_available() -> bool:
    try:
        cp = subprocess.run(["docker", "version"], capture_output=True, text=True, check=False, timeout=8)
        return cp.returncode == 0
    except OSError:
        return False


def run_in_docker(
    *,
    repo_root: Path,
    image: str,
    command: list[str],
    timeout_s: int = 60,
    cpus: str = "1",
    memory: str = "512m",
) -> SandboxResult:
    if not _docker_available():
        return SandboxResult(ok=False, exit_code=127, stdout="", stderr="", error="docker_not_available")

    repo_root = repo_root.resolve()
    workdir = "/workspace"

    # Mount repo read-write so results can be written under results/.
    cmd = [
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "--cpus",
        cpus,
        "--memory",
        memory,
        "-v",
        f"{repo_root}:{workdir}",
        "-w",
        workdir,
        image,
        *command,
    ]

    try:
        cp = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=timeout_s)
    except subprocess.TimeoutExpired as exc:
        return SandboxResult(ok=False, exit_code=124, stdout=exc.stdout or "", stderr=exc.stderr or "", error="timeout")
    except OSError as exc:
        return SandboxResult(ok=False, exit_code=127, stdout="", stderr=str(exc), error="exec_error")

    return SandboxResult(ok=(cp.returncode == 0), exit_code=cp.returncode, stdout=cp.stdout or "", stderr=cp.stderr or "")


def get_sandbox_mode() -> str:
    # local | docker
    # Production switch: if PRODUCTION=1, default to docker unless explicitly overridden.
    if os.getenv("PRODUCTION", "").strip() == "1" and not os.getenv("SANDBOX_MODE", "").strip():
        return "docker"
    return os.getenv("SANDBOX_MODE", "local").strip().lower()


def get_docker_image() -> str:
    return os.getenv("GRADER_DOCKER_IMAGE", "assignment-grader:latest").strip()


def get_docker_image_for_language(language: str) -> str:
    """Allow selecting per-language images if desired.

    Env precedence:
      GRADER_DOCKER_IMAGE_<LANG> (e.g. GRADER_DOCKER_IMAGE_CPP)
      GRADER_DOCKER_IMAGE
    """
    lang = (language or "").strip().lower()
    key = f"GRADER_DOCKER_IMAGE_{lang.upper()}"
    specific = os.getenv(key, "").strip()
    return specific or get_docker_image()
