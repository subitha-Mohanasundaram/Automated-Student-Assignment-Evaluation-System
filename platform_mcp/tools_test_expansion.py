from __future__ import annotations

import json
import random
from datetime import datetime
from pathlib import Path
from typing import Any


def _load_problem(problem_id: str) -> dict[str, Any]:
    path = Path("problems") / problem_id / "problem.json"
    if not path.exists():
        raise FileNotFoundError(f"Problem not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _infer_mode(problem: dict[str, Any]) -> str:
    java = problem.get("java") if isinstance(problem.get("java"), dict) else {}
    contract = java.get("contract") if isinstance(java.get("contract"), dict) else {}
    mode = contract.get("mode")
    return str(mode) if isinstance(mode, str) else "numeric_binary"


def _gen_addition_cases(n: int) -> list[list[object]]:
    cases: list[list[object]] = []
    # A few deterministic edge cases first.
    fixed = [
        [0.0, 0.0, 0.0],
        [-1.0, 1.0, 0.0],
        [999999.0, 1.0, 1000000.0],
        [-999999.0, -1.0, -1000000.0],
    ]
    for item in fixed[: max(0, min(len(fixed), n))]:
        cases.append(item)
    for _ in range(max(0, n - len(cases))):
        a = random.randint(-1_000_000, 1_000_000)
        b = random.randint(-1_000_000, 1_000_000)
        cases.append([float(a), float(b), float(a + b)])
    return cases


def _gen_reverse_string_cases(n: int) -> list[list[object]]:
    fixed = ["", "a", "racecar", "  spaced  ", "hello!", "AaBbCc"]
    out: list[list[object]] = []
    for s in fixed[: max(0, min(len(fixed), n))]:
        out.append([s, s[::-1]])
    for _ in range(max(0, n - len(out))):
        length = random.choice([0, 1, 2, 5, 10, 50, 200])
        s = "".join(random.choice("abcxyzABCXYZ0123 !?") for _ in range(length))
        out.append([s, s[::-1]])
    return out


def _parse_pipe_pair(s: str) -> tuple[str, str]:
    if "|" not in s:
        return s, ""
    a, b = s.split("|", 1)
    return a, b


def _gen_anagram_cases(n: int) -> list[list[object]]:
    fixed = [
        ("listen", "silent"),
        ("rat", "car"),
        ("evil", "vile"),
        ("aabb", "ab"),
        ("", ""),
    ]
    out: list[list[object]] = []
    for a, b in fixed[: max(0, min(len(fixed), n))]:
        ok = sorted(a) == sorted(b)
        out.append([f"{a}|{b}", "true" if ok else "false"])
    for _ in range(max(0, n - len(out))):
        # Generate by shuffling (true) or mutating (false)
        base = "".join(random.choice("abcdxyz") for _ in range(random.choice([0, 1, 2, 5, 10])))
        if random.random() < 0.5:
            b = "".join(random.sample(list(base), k=len(base))) if base else ""
        else:
            b = base + random.choice("pq")
        ok = sorted(base) == sorted(b)
        out.append([f"{base}|{b}", "true" if ok else "false"])
    return out


def _rotate_left(nums: list[int], k: int) -> list[int]:
    if not nums:
        return nums
    k = k % len(nums)
    return nums[k:] + nums[:k]


def _gen_left_rotation_cases(n: int) -> list[list[object]]:
    fixed = [
        ([1, 2, 3, 4, 5], 2),
        ([10, 20, 30], 1),
        ([1, 2, 3], 0),
        ([7, 8, 9, 10], 5),
    ]
    out: list[list[object]] = []
    for nums, k in fixed[: max(0, min(len(fixed), n))]:
        exp = " ".join(str(x) for x in _rotate_left(nums, k))
        out.append([f"{' '.join(map(str, nums))}|{k}", exp])
    for _ in range(max(0, n - len(out))):
        size = random.choice([0, 1, 2, 3, 5, 10])
        nums = [random.randint(-50, 50) for _ in range(size)]
        k = random.randint(0, 30)
        exp = " ".join(str(x) for x in _rotate_left(nums, k))
        out.append([f"{' '.join(map(str, nums))}|{k}", exp])
    return out


def _lcp(strings: list[str]) -> str:
    if not strings:
        return ""
    pref = strings[0]
    for s in strings[1:]:
        while not s.startswith(pref) and pref:
            pref = pref[:-1]
        if not pref:
            return ""
    return pref


def _gen_lcp_cases(n: int) -> list[list[object]]:
    fixed = [
        (["flower", "flow", "flight"], "fl"),
        (["dog", "racecar", "car"], ""),
        (["interview", "interval", "internal"], "inter"),
        (["a", "ab", "abc"], "a"),
        ([], ""),
    ]
    out: list[list[object]] = []
    for items, exp in fixed[: max(0, min(len(fixed), n))]:
        out.append([",".join(items), exp])
    for _ in range(max(0, n - len(out))):
        count = random.choice([0, 1, 2, 3, 5])
        base = "".join(random.choice("abcxyz") for _ in range(random.choice([0, 1, 2, 3])))
        items = []
        for _j in range(count):
            tail = "".join(random.choice("abcxyz") for _ in range(random.choice([0, 1, 2, 3, 5])))
            items.append(base + tail)
        out.append([",".join(items), _lcp(items)])
    return out


def _two_sum_indices(nums: list[int], target: int) -> str:
    seen: dict[int, int] = {}
    for i, x in enumerate(nums):
        need = target - x
        if need in seen:
            return f"{seen[need]} {i}"
        if x not in seen:
            seen[x] = i
    return ""


def _gen_two_sum_cases(n: int) -> list[list[object]]:
    fixed = [
        ([2, 7, 11, 15], 9, "0 1"),
        ([3, 2, 4], 6, "1 2"),
        ([3, 3], 6, "0 1"),
        ([1, 5, 1, 5], 10, "1 3"),
    ]
    out: list[list[object]] = []
    for nums, target, exp in fixed[: max(0, min(len(fixed), n))]:
        out.append([f"{' '.join(map(str, nums))}|{target}", exp])
    for _ in range(max(0, n - len(out))):
        size = random.choice([2, 3, 5, 10])
        nums = [random.randint(-20, 20) for _ in range(size)]
        # Ensure at least one solution by constructing a pair.
        i, j = 0, 1
        target = nums[i] + nums[j]
        exp = _two_sum_indices(nums, target)
        if not exp:
            exp = f"{i} {j}"
        out.append([f"{' '.join(map(str, nums))}|{target}", exp])
    return out


def generate_hidden_test_expansion(*, problem_id: str, count: int = 10) -> dict[str, Any]:
    problem = _load_problem(problem_id)
    mode = _infer_mode(problem)

    pid = str(problem.get("problem_id") or problem_id)
    # Generate expected-output cases for known built-in problems so they can be used for scoring.
    if pid in {"add_numbers", "swap_numbers"}:
        extra = _gen_addition_cases(count)
        kind = "numeric_binary"
    elif pid == "reverse_string":
        extra = _gen_reverse_string_cases(count)
        kind = "string_unary"
    elif pid == "anagram_check":
        extra = _gen_anagram_cases(count)
        kind = "string_unary"
    elif pid == "left_rotation":
        extra = _gen_left_rotation_cases(count)
        kind = "string_unary"
    elif pid == "longest_common_prefix":
        extra = _gen_lcp_cases(count)
        kind = "string_unary"
    elif pid == "two_sum":
        extra = _gen_two_sum_cases(count)
        kind = "string_unary"
    else:
        # Fallback: generate numeric addition-like cases if the contract is numeric_binary.
        if mode == "numeric_binary":
            extra = _gen_addition_cases(count)
            kind = "numeric_binary"
        else:
            # Unknown string-unary problem: generate no scoring cases.
            extra = []
            kind = "unsupported"

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out_dir = Path("results") / "generated_tests"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{problem_id}_{kind}_{ts}.json"
    out_path.write_text(json.dumps({"problem_id": problem_id, "kind": kind, "mode": mode, "cases": extra}, indent=2), encoding="utf-8")

    return {
        "success": True,
        "details": {
            "problem_id": problem_id,
            "kind": kind,
            "mode": mode,
            "path": str(out_path),
            "count": len(extra),
            "scorable": bool(extra),
        },
    }
