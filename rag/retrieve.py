"""Retrieve the most relevant problem spec chunk from ChromaDB.

Usage:
    from rag.retrieve import get_problem_context
    context = get_problem_context("two_sum")
"""

from __future__ import annotations

import json
from pathlib import Path

try:
    import chromadb
    from chromadb.utils import embedding_functions as ef
except ImportError:  # pragma: no cover
    chromadb = None  # type: ignore[assignment]
    ef = None  # type: ignore[assignment]

_STORE_DIR = Path(__file__).parent.parent / ".chroma_db"
_COLLECTION_NAME = "problems"

# Fallback: load directly from problem.json when ChromaDB isn't available or
# the store hasn't been built yet (e.g., first CI run before build_store runs).
_PROBLEMS_DIR = Path(__file__).parent.parent / "problems"


def _load_direct(problem_id: str) -> str:
    """Read problem.json directly without ChromaDB."""
    from rag.problem_store import _make_doc_text  # local import avoids circular

    path = _PROBLEMS_DIR / problem_id / "problem.json"
    if not path.exists():
        return f"Problem spec not found for: {problem_id}"
    raw = json.loads(path.read_text(encoding="utf-8"))
    return _make_doc_text(raw)


def get_problem_context(problem_id: str, n_results: int = 1) -> str:
    """Return a text chunk describing the problem spec.

    Tries ChromaDB first; falls back to direct JSON read if the store is
    unavailable or empty.
    """
    if chromadb is None:
        return _load_direct(problem_id)

    persist_path = _STORE_DIR
    if not persist_path.exists():
        return _load_direct(problem_id)

    try:
        emb_fn = ef.DefaultEmbeddingFunction()
        client = chromadb.PersistentClient(path=str(persist_path))
        collection = client.get_or_create_collection(
            name=_COLLECTION_NAME,
            embedding_function=emb_fn,
        )

        # Try exact ID fetch first (fast, no embedding needed).
        try:
            result = collection.get(ids=[problem_id], include=["documents"])
            docs = result.get("documents") or []
            if docs and docs[0]:
                return docs[0]
        except Exception:
            pass

        # Fall back to similarity search using problem_id as the query text.
        result = collection.query(query_texts=[problem_id], n_results=n_results, include=["documents"])
        docs = result.get("documents") or []
        if docs and docs[0]:
            return docs[0][0] if isinstance(docs[0], list) else docs[0]
    except Exception:
        pass

    return _load_direct(problem_id)
