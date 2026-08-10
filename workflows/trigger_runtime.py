"""
workflows/trigger_runtime.py
=============================
Trigger Runtime — cron, webhook, and manual trigger scheduler.

Reads all saved workflows, inspects their triggers, and:
  - Schedules cron triggers via APScheduler
  - Registers webhook trigger endpoints (via web_app.py)
  - Provides a manual-trigger API for the existing /api/workflows/:id/run route

Lifecycle:
    runtime = TriggerRuntime()
    runtime.start()          # call on FastAPI startup
    runtime.stop()           # call on FastAPI shutdown
    runtime.reload()         # call after a workflow is saved/updated
"""
from __future__ import annotations

import json
import logging
import re
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_WF_DIR = Path("workflows") / "saved"


def _all_workflows() -> List[Dict]:
    """Load all saved workflow JSON files."""
    if not _WF_DIR.exists():
        return []
    result = []
    for p in _WF_DIR.glob("*.json"):
        try:
            with p.open(encoding="utf-8") as f:
                result.append(json.load(f))
        except Exception:
            pass
    return result


def _parse_cron(expr: str) -> Optional[Dict]:
    """
    Parse a cron expression into APScheduler CronTrigger kwargs.
    Supports standard 5-field cron: minute hour day month day_of_week
    """
    parts = expr.strip().split()
    if len(parts) != 5:
        return None
    keys = ["minute", "hour", "day", "month", "day_of_week"]
    return dict(zip(keys, parts))


class TriggerRuntime:
    """
    Manages workflow trigger scheduling.
    Thread-safe — can be reloaded at runtime when workflows change.
    """

    def __init__(self) -> None:
        self._scheduler = None
        self._lock      = threading.Lock()
        self._running   = False
        # webhook_path → (workflow_id, trigger_id)
        self._webhook_map: Dict[str, tuple] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the scheduler and load all workflows."""
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            self._scheduler = BackgroundScheduler(timezone="UTC")
            self._scheduler.start()
            self._running = True
            logger.info("TriggerRuntime: scheduler started")
            self.reload()
        except ImportError:
            logger.warning("TriggerRuntime: APScheduler not installed — cron triggers disabled")
        except Exception as e:
            logger.error("TriggerRuntime: failed to start: %s", e)

    def stop(self) -> None:
        """Gracefully shut down the scheduler."""
        if self._scheduler and self._running:
            try:
                self._scheduler.shutdown(wait=False)
            except Exception:
                pass
            self._running = False
            logger.info("TriggerRuntime: scheduler stopped")

    def reload(self) -> None:
        """Re-scan all workflows and reschedule cron jobs."""
        if not self._running or not self._scheduler:
            return
        with self._lock:
            self._scheduler.remove_all_jobs()
            self._webhook_map.clear()
            for wf in _all_workflows():
                self._register_workflow(wf)
        logger.info("TriggerRuntime: reloaded — %d job(s) scheduled, %d webhook(s) registered",
                    len(self._scheduler.get_jobs()), len(self._webhook_map))

    # ------------------------------------------------------------------
    # Webhook lookup (used by web_app.py)
    # ------------------------------------------------------------------

    def get_webhook_workflow(self, path: str) -> Optional[tuple]:
        """Return (workflow_id, trigger_id) for a registered webhook path, or None."""
        return self._webhook_map.get(path)

    @property
    def webhook_paths(self) -> Dict[str, tuple]:
        return dict(self._webhook_map)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _register_workflow(self, wf: Dict) -> None:
        wf_id = wf.get("id") or wf.get("workflow_id")
        if not wf_id:
            return
        for trigger in wf.get("triggers", []):
            t_type = trigger.get("type", "")
            t_id   = trigger.get("id", "trigger")

            if t_type == "cron":
                self._schedule_cron(wf, trigger)

            elif t_type == "webhook":
                path = trigger.get("webhook_path") or f"/webhooks/{wf_id}/{t_id}"
                self._webhook_map[path] = (wf_id, t_id)
                logger.info("  Webhook trigger registered: %s → workflow %s", path, wf_id)

    def _schedule_cron(self, wf: Dict, trigger: Dict) -> None:
        """Add a cron job for the given trigger."""
        expr = trigger.get("cron_expression") or trigger.get("schedule", "")
        if not expr:
            return
        cron_kwargs = _parse_cron(expr)
        if not cron_kwargs:
            logger.warning("TriggerRuntime: invalid cron '%s' in workflow %s",
                           expr, wf.get("id"))
            return
        wf_id = wf.get("id") or wf.get("workflow_id")
        job_id = f"cron_{wf_id}_{trigger.get('id', 'trigger')}"

        def _fire():
            try:
                from workflows.executor import start_run
                run_id = start_run(wf, dry_run=False, inputs={"_trigger": "cron"})
                logger.info("TriggerRuntime: cron fired workflow %s → run %s", wf_id, run_id)
            except Exception as exc:
                logger.error("TriggerRuntime: cron fire failed for %s: %s", wf_id, exc)

        try:
            from apscheduler.triggers.cron import CronTrigger
            self._scheduler.add_job(
                _fire,
                CronTrigger(**cron_kwargs, timezone="UTC"),
                id=job_id,
                replace_existing=True,
                misfire_grace_time=60,
            )
            logger.info("  Cron trigger scheduled: %s @ '%s'", wf_id, expr)
        except Exception as e:
            logger.error("TriggerRuntime: could not schedule cron for %s: %s", wf_id, e)


# ── Module-level singleton ──────────────────────────────────────
TRIGGER_RUNTIME: Optional[TriggerRuntime] = None


def get_runtime() -> TriggerRuntime:
    global TRIGGER_RUNTIME
    if TRIGGER_RUNTIME is None:
        TRIGGER_RUNTIME = TriggerRuntime()
    return TRIGGER_RUNTIME
