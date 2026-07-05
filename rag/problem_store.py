"""Build or rebuild the ChromaDB vector store from problems/*/problem.json.

Run once locally or at CI start:
    python -m rag.problem_store

The store is persisted to .chroma_db/ (git-ignored). On CI it rebuilds in
~seconds from the committed problem.json files — no pre-built store needed.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

# ChromaDB is optional at import time so evaluator.py stays importable without it.
try:
    import chromadb
    from chromadb.utils import embedding_functions as ef
except ImportError:  # pragma: no cover
    chromadb = None  # type: ignore[assignment]
    ef = None  # type: ignore[assignment]

_STORE_DIR = Path(__file__).parent.parent / ".chroma_db"
_COLLECTION_NAME = "problems"


def _make_doc_text(raw: dict) -> str:
    """Render a problem.json dict into a plain-text chunk suitable for embedding."""
    pid = raw.get("problem_id", "unknown")
    title = raw.get("title", pid.replace("_", " ").title())
    description = raw.get("description", "")
    constraints = raw.get("constraints", "")
    rubric = raw.get("rubric", "")
    examples = raw.get("examples", "")

    # Build visible test case pairs as natural-language examples when no
    # human-readable description is present in the JSON.
    java_visible = raw.get("java", {}).get("visible_cases", [])
    case_lines: list[str] = []
    for case in java_visible[:3]:  # cap at 3 to keep chunks short
        if isinstance(case, list) and len(case) >= 2:
            case_lines.append(f"  Input: {case[0]}  →  Output: {case[1]}")
    case_text = "\n".join(case_lines) if case_lines else ""

    parts = [f"Problem: {title}", f"ID: {pid}"]
    if description:
        parts.append(f"Description: {description}")
    if constraints:
        parts.append(f"Constraints: {constraints}")
    if rubric:
        parts.append(f"Rubric: {rubric}")
    if examples:
        parts.append(f"Examples: {examples}")
    if case_text:
        parts.append(f"Sample cases:\n{case_text}")
    return "\n".join(parts)


def build_store(problems_dir: Path | None = None, store_dir: Path | None = None) -> None:
    """Index all problem.json files into a persistent ChromaDB collection.

    Safe to call multiple times — upserts existing documents.
    """
    if chromadb is None:
        raise ImportError("chromadb is not installed. Run: pip install chromadb")

    problems_root = problems_dir or (Path(__file__).parent.parent / "problems")
    persist_path = store_dir or _STORE_DIR
    persist_path.mkdir(parents=True, exist_ok=True)

    # Use a lightweight sentence-transformers model so we don't need an API key
    # for the embedding step.  Falls back to the default (all-MiniLM-L6-v2).
    emb_fn = ef.DefaultEmbeddingFunction()

    client = chromadb.PersistentClient(path=str(persist_path))
    collection = client.get_or_create_collection(
        name=_COLLECTION_NAME,
        embedding_function=emb_fn,
    )

    problem_dirs = [p for p in problems_root.iterdir() if p.is_dir() and (p / "problem.json").exists()]
    if not problem_dirs:
        print(f"[problem_store] No problem.json files found under {problems_root}")
        return

    docs: list[str] = []
    ids: list[str] = []
    metas: list[dict] = []

    for pdir in sorted(problem_dirs):
        raw = json.loads((pdir / "problem.json").read_text(encoding="utf-8"))
        pid = raw.get("problem_id", pdir.name)
        doc_text = _make_doc_text(raw)
        docs.append(doc_text)
        ids.append(pid)
        metas.append({"problem_id": pid, "source": str(pdir / "problem.json")})

    collection.upsert(documents=docs, ids=ids, metadatas=metas)
    print(f"[problem_store] Indexed {len(docs)} problem(s) into {persist_path}")


if __name__ == "__main__":
    build_store()
    print("[problem_store] Done.")
