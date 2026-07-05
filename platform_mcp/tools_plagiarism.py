from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

import difflib


def _tokenize_basic(text: str) -> list[str]:
    # Language-agnostic light tokenizer
    text = re.sub(r"//.*", "", text)
    text = re.sub(r"/\\*.*?\\*/", "", text, flags=re.DOTALL)
    text = re.sub(r"#.*", "", text)
    return re.findall(r"[A-Za-z_][A-Za-z_0-9]*|\\d+|==|!=|<=|>=|[{}()\\[\\];,]", text)


def _fingerprint_tokens(tokens: list[str]) -> str:
    joined = " ".join(tokens).lower().encode("utf-8")
    return hashlib.sha256(joined).hexdigest()


def detect_plagiarism(*, submission_path: str, corpus_dir: str = "submissions", threshold: float = 0.8) -> dict[str, Any]:
    path = Path(submission_path).resolve()
    if not path.exists():
        return {"success": False, "error": "file_not_found", "details": {"path": str(path)}}

    source = path.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")
    tokens = _tokenize_basic(source)
    fp = _fingerprint_tokens(tokens)

    corpus = Path(corpus_dir)
    matches: list[dict[str, Any]] = []
    if corpus.exists():
        for other in corpus.rglob(f"*{path.suffix}"):
            other = other.resolve()
            if other == path:
                continue
            try:
                other_src = other.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")
            except OSError:
                continue
            other_tokens = _tokenize_basic(other_src)
            other_fp = _fingerprint_tokens(other_tokens)
            if other_fp == fp:
                matches.append({"path": str(other), "similarity": 1.0, "reason": "exact_token_fingerprint"})
                continue
            ratio = difflib.SequenceMatcher(None, " ".join(tokens), " ".join(other_tokens)).ratio()
            if ratio >= float(threshold):
                matches.append({"path": str(other), "similarity": round(ratio, 3), "reason": "sequence_match"})

    flagged = any(m["similarity"] >= float(threshold) for m in matches)
    best = max((m["similarity"] for m in matches), default=0.0)
    return {
        "success": True,
        "flagged": flagged,
        "similarity_best": best,
        "details": {"threshold": threshold, "matches": sorted(matches, key=lambda x: x["similarity"], reverse=True)[:10]},
    }

