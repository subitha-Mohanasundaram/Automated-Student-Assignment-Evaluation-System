from __future__ import annotations

import json
import os
import random
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Any

from assignment_intel.db import enqueue_job, get_assignment, set_assignment_generation_status, upsert_assignment
from assignment_intel.problem_sources import ensure_default_catalogs, load_catalog


@dataclass(frozen=True)
class DailyAssignResult:
    assignment_id: str
    job_id: int
    source: str
    seed_id: str
    title: str


def _utcnow() -> datetime:
    return datetime.utcnow()


def _state_path() -> Path:
    return Path(os.environ.get("DAILY_ASSIGN_STATE_FILE", "results/auto_assign_state.json"))


def _catalog_dir() -> Path:
    return Path(os.environ.get("DAILY_ASSIGN_CATALOG_DIR", "problems/sources"))


def _parse_sources() -> list[str]:
    raw = os.environ.get("DAILY_ASSIGN_SOURCES", "leetcode,geeksforgeeks,neetcode,hackerearth")
    xs = [x.strip().lower().replace(" ", "_") for x in raw.split(",") if x.strip()]
    return xs or ["leetcode"]


def _parse_time_utc() -> time:
    raw = os.environ.get("DAILY_ASSIGN_AT_UTC", "07:00").strip()
    try:
        hh, mm = raw.split(":", 1)
        return time(hour=max(0, min(23, int(hh))), minute=max(0, min(59, int(mm))))
    except Exception:
        return time(7, 0)


def _load_state() -> dict[str, Any]:
    p = _state_path()
    if not p.exists():
        return {"last_date": "", "rotation_index": 0, "recent_seed_ids": []}
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        obj = {}
    if not isinstance(obj, dict):
        obj = {}
    obj.setdefault("last_date", "")
    obj.setdefault("rotation_index", 0)
    obj.setdefault("recent_seed_ids", [])
    if not isinstance(obj.get("recent_seed_ids"), list):
        obj["recent_seed_ids"] = []
    return obj


def _save_state(st: dict[str, Any]) -> None:
    p = _state_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(st, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")


def _slugify(s: str) -> str:
    s = (s or "").strip().lower()
    out: list[str] = []
    prev_us = False
    for ch in s:
        ok = ("a" <= ch <= "z") or ("0" <= ch <= "9")
        if ok:
            out.append(ch)
            prev_us = False
        else:
            if not prev_us:
                out.append("_")
                prev_us = True
    slug = "".join(out).strip("_")
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug or "daily_problem"


def _pick_seed(source: str, *, recent: set[str], catalog_dir: Path) -> tuple[str, str, str]:
    # Returns (seed_id, title, description)
    seeds = load_catalog(source, catalog_dir=catalog_dir)
    if not seeds:
        # If the catalog is missing, we still return a seed.
        return (f"{source}:fallback", f"Daily {source.title()} Problem", f"Create a daily coding problem (source: {source}).")

    candidates = [s for s in seeds if str(s.seed_id) not in recent]
    if not candidates:
        candidates = seeds
    s = random.choice(candidates)
    return (str(s.seed_id), str(s.title), str(s.description))


def maybe_create_daily_assignment(*, now_utc: datetime | None = None, force: bool = False) -> DailyAssignResult | None:
    """Create a new assignment at most once per UTC day.

    Behavior:
    - rotates through sources (round-robin)
    - picks a random seed from that source's catalog
    - saves an assignment and enqueues the normal `problem_generation` job

    Requires:
    - worker.py running (to consume queued jobs)
    - OpenAI configured (AI_PROVIDER=openai and OPENAI_API_KEY set)
    """

    if os.environ.get("DAILY_ASSIGN_ENABLED", "0").strip() not in {"1", "true", "yes", "on"}:
        return None

    now = now_utc or _utcnow()
    today = now.date().isoformat()
    at_utc = _parse_time_utc()

    st = _load_state()
    last_date = str(st.get("last_date") or "")

    if not force:
        if last_date == today:
            return None
        if now.time() < at_utc:
            return None

    # Ensure catalogs exist so it works on a fresh checkout.
    catalog_dir = _catalog_dir()
    ensure_default_catalogs(catalog_dir)

    sources = _parse_sources()
    idx = int(st.get("rotation_index") or 0)
    source = sources[idx % len(sources)]

    recent_list = [str(x) for x in (st.get("recent_seed_ids") or []) if str(x)]
    recent = set(recent_list)

    seed_id, title, desc = _pick_seed(source, recent=recent, catalog_dir=catalog_dir)

    # Build a unique assignment id.
    base = _slugify(title)
    aid = f"{base}_{now.strftime('%Y%m%d')}"
    if get_assignment(assignment_id=aid):
        aid = f"{aid}_{random.randint(1000, 9999)}"

    upsert_assignment(assignment_id=aid, title=title.strip(), description=desc.strip())

    # If AI isn't configured, mark failed (matches instructor save behavior).
    if os.getenv("AI_PROVIDER", "null").strip().lower() != "openai" or not os.getenv("OPENAI_API_KEY", "").strip():
        set_assignment_generation_status(assignment_id=aid, status="failed", error="openai_not_configured", active=False)
        # Still update state so we don't spam-create failing assignments.
        st["last_date"] = today
        st["rotation_index"] = idx + 1
        st["recent_seed_ids"] = (recent_list + [seed_id])[-50:]
        _save_state(st)
        return DailyAssignResult(assignment_id=aid, job_id=0, source=source, seed_id=seed_id, title=title)

    set_assignment_generation_status(assignment_id=aid, status="queued", error=None, active=False)
    job_id = enqueue_job(job_type="problem_generation", payload={"assignment_id": aid})

    st["last_date"] = today
    st["rotation_index"] = idx + 1
    st["recent_seed_ids"] = (recent_list + [seed_id])[-50:]
    _save_state(st)

    return DailyAssignResult(assignment_id=aid, job_id=job_id, source=source, seed_id=seed_id, title=title)


def tick(*, min_interval_s: float = 30.0) -> None:
    """Called from the long-running worker loop."""

    # Keep next check time in module state.
    # Using an attribute avoids introducing a new DB table.
    last = getattr(tick, "_last", None)
    now = _utcnow()
    if isinstance(last, datetime) and (now - last) < timedelta(seconds=float(min_interval_s)):
        return
    setattr(tick, "_last", now)
    try:
        maybe_create_daily_assignment(now_utc=now, force=False)
    except Exception:
        # Never crash the worker because of auto-assign.
        return
