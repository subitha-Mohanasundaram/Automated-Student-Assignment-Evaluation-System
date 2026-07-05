from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any

from assignment_intel.sandbox_runner import get_docker_image_for_language, run_in_docker


def _now_ms() -> int:
    return int(time.time() * 1000)


def _safe_json_load(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Attempt to extract the first JSON object in the text.
        m = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                return {}
        return {}


def _require_openai() -> tuple[str, str] | None:
    if os.getenv("AI_PROVIDER", "null").strip().lower() != "openai":
        return None
    key = os.getenv("OPENAI_API_KEY", "").strip()
    model = os.getenv("OPENAI_MODEL", "gpt-5").strip()
    if not key:
        return None
    return key, model


def _openai_json(*, system: str, user: str) -> dict[str, Any]:
    cfg = _require_openai()
    if not cfg:
        return {"ok": False, "error": "openai_not_configured"}
    try:
        from openai import OpenAI
    except Exception as exc:
        return {"ok": False, "error": f"openai_sdk_missing: {exc}"}

    _key, model = cfg
    client = OpenAI()
    resp = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    text = getattr(resp, "output_text", "") or ""
    obj = _safe_json_load(text)
    if not obj:
        return {"ok": False, "error": "bad_json", "raw": text[:2000]}
    return {"ok": True, "data": obj}


def generate_problem_metadata(*, title: str, problem_description: str) -> dict[str, Any]:
    system = (
        "You are generating metadata for a coding interview style problem.\n"
        "Return ONLY JSON with keys:\n"
        "- generated_description (string; polished full problem statement)\n"
        "- input_format (string)\n"
        "- output_format (string)\n"
        "- constraints (string)\n"
        "- examples (array of {input, output, explanation})\n"
        "- difficulty (easy|medium|hard)\n"
        "- tags (array of strings)\n"
        "Keep examples minimal and consistent with stdin/stdout style problems."
    )
    user = json.dumps({"title": title, "problem_description": problem_description})
    res = _openai_json(system=system, user=user)
    if not res.get("ok"):
        return {"success": False, "error": res.get("error"), "details": res}
    data = res["data"]
    return {"success": True, "details": data}


def generate_reference_solution(*, title: str, problem_description: str, constraints: str = "", examples: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    system = (
        "Write a correct Python reference solution for a stdin/stdout coding problem.\n"
        "Return ONLY JSON with keys: language (always 'python'), code (a complete program reading stdin and printing stdout).\n"
        "Do not include markdown."
    )
    user = json.dumps(
        {
            "title": title,
            "problem_description": problem_description,
            "constraints": constraints,
            "examples": examples or [],
        }
    )
    res = _openai_json(system=system, user=user)
    if not res.get("ok"):
        return {"success": False, "error": res.get("error"), "details": res}
    data = res["data"]
    code = str(data.get("code") or "")
    if not code.strip():
        return {"success": False, "error": "empty_reference_solution"}
    return {"success": True, "details": {"language": "python", "code": code}}


def generate_test_cases(
    *,
    title: str,
    problem_description: str,
    constraints: str = "",
    difficulty: str = "medium",
    visible_count: int = 3,
    hidden_count: int = 10,
    stress_count: int = 20,
) -> dict[str, Any]:
    system = (
        "Generate diverse stdin inputs for the problem. Return ONLY JSON with keys:\n"
        "visible_inputs (array of strings), hidden_inputs (array of strings), stress_inputs (array of strings).\n"
        "Each string must be exactly what would be provided on stdin for one run."
    )
    user = json.dumps(
        {
            "title": title,
            "problem_description": problem_description,
            "constraints": constraints,
            "difficulty": difficulty,
            "visible_count": visible_count,
            "hidden_count": hidden_count,
            "stress_count": stress_count,
        }
    )
    res = _openai_json(system=system, user=user)
    if not res.get("ok"):
        return {"success": False, "error": res.get("error"), "details": res}
    data = res["data"]
    return {"success": True, "details": data}


def compute_expected_outputs(*, reference_solution_code: str, inputs: list[str], timeout_s: int = 8) -> dict[str, Any]:
    # Always compute in Docker for safety.
    repo_root = Path(__file__).resolve().parent.parent
    tmp_dir = Path("sandbox_tmp") / f"ref_{_now_ms()}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    ref_path = tmp_dir / "reference.py"
    ref_path.write_text(reference_solution_code, encoding="utf-8")

    try:
        rel = ref_path.resolve().relative_to(repo_root)
    except Exception as exc:
        return {"success": False, "error": "path_error", "details": {"message": str(exc), "path": str(ref_path)}}

    image = get_docker_image_for_language("python")
    outputs: list[str] = []
    for i, inp in enumerate(inputs):
        in_path = tmp_dir / f"in_{i}.txt"
        in_path.write_text(str(inp), encoding="utf-8")
        try:
            in_rel = in_path.resolve().relative_to(repo_root)
        except Exception as exc:
            return {"success": False, "error": "path_error", "details": {"message": str(exc), "path": str(in_path)}}

        cmd = [
            "bash",
            "-lc",
            f"cd /workspace && python {str(rel).replace('\\\\','/')} < {str(in_rel).replace('\\\\','/')}",
        ]
        res = run_in_docker(repo_root=repo_root, image=image, command=cmd, timeout_s=timeout_s, cpus="1", memory="512m")
        if not res.ok:
            return {"success": False, "error": "reference_solution_failed", "details": {"stdout": res.stdout, "stderr": res.stderr}}
        outputs.append((res.stdout or "").replace("\r\n", "\n").strip())

    return {"success": True, "details": {"outputs": outputs}}
