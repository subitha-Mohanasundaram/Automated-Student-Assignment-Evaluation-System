from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ProblemSeed:
    """A minimal seed used to generate a full assignment via the AI pipeline.

    We intentionally keep this small: the AI pipeline will generate constraints,
    examples, tests, and a reference solution.
    """

    source: str
    seed_id: str
    title: str
    description: str
    url: str | None = None


def _norm_source(s: str) -> str:
    return (s or "").strip().lower().replace(" ", "_")


def load_catalog(source: str, *, catalog_dir: Path) -> list[ProblemSeed]:
    """Load seeds from `catalog_dir/<source>.json`.

    File format:
    [
      {"id": "two-sum", "title": "...", "description": "...", "url": "https://..."},
      ...
    ]
    """

    src = _norm_source(source)
    p = Path(catalog_dir) / f"{src}.json"
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(data, list):
        return []

    out: list[ProblemSeed] = []
    for i, row in enumerate(data):
        if not isinstance(row, dict):
            continue
        sid = str(row.get("id") or f"{src}:{i}").strip()
        title = str(row.get("title") or "").strip()
        desc = str(row.get("description") or "").strip()
        url = str(row.get("url") or "").strip() or None
        if not title:
            continue
        if not desc:
            # Keep a non-empty prompt for the generation agent.
            desc = f"Create a coding problem similar to '{title}' (source: {src})."
            if url:
                desc += f" Reference URL: {url}"
        out.append(ProblemSeed(source=src, seed_id=sid, title=title, description=desc, url=url))
    return out


def ensure_default_catalogs(catalog_dir: Path) -> None:
    """Create tiny starter catalogs so daily assignment works out-of-the-box.

    In production, replace these with your own curated lists or importer.
    """

    catalog_dir = Path(catalog_dir)
    catalog_dir.mkdir(parents=True, exist_ok=True)

    defaults: dict[str, list[dict[str, Any]]] = {
        "leetcode": [
            {
                "id": "two-sum",
                "title": "Two Sum",
                "description": "Given an array of integers and a target, return indices of two numbers that add up to the target.",
                "url": "https://leetcode.com/problems/two-sum/",
            },
            {
                "id": "valid-parentheses",
                "title": "Valid Parentheses",
                "description": "Given a string with parentheses/brackets/braces, determine if it is valid.",
                "url": "https://leetcode.com/problems/valid-parentheses/",
            },
        ],
        "geeksforgeeks": [
            {
                "id": "reverse-words",
                "title": "Reverse Words in a Given String",
                "description": "Reverse words in a string separated by dots/spaces (handle edge cases).",
                "url": "https://www.geeksforgeeks.org/reverse-words-in-a-given-string/",
            }
        ],
        "neetcode": [
            {
                "id": "contains-duplicate",
                "title": "Contains Duplicate",
                "description": "Return true if any value appears at least twice in the array.",
                "url": "https://neetcode.io/problems/contains-duplicate",
            }
        ],
        "hackerearth": [
            {
                "id": "monk-and-rotation",
                "title": "Monk and Rotation",
                "description": "Perform right rotations on an array and output the final configuration.",
                "url": "https://www.hackerearth.com/problem/algorithm/monk-and-rotation-3/",
            }
        ],
    }

    for src, rows in defaults.items():
        p = catalog_dir / f"{src}.json"
        if p.exists():
            continue
        try:
            p.write_text(json.dumps(rows, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        except Exception:
            pass
