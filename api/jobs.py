"""In-process background job registry for company processing.

Single concurrent job (a global lock) protects the Ollama free-tier quota and
shared resources; additional requests queue behind it. Jobs are tracked in a
module dict and polled via GET /jobs/{id}.
"""

from __future__ import annotations

import threading
import time
import uuid

_jobs: dict[str, dict] = {}
_lock = threading.Lock()
_run_lock = threading.Lock()  # enforces one processing job at a time


def _set(job_id: str, **kw) -> None:
    with _lock:
        if job_id in _jobs:
            _jobs[job_id].update(kw)


def get_job(job_id: str) -> dict | None:
    with _lock:
        j = _jobs.get(job_id)
        return dict(j) if j else None


def start_processing(ticker: str, *, force: bool = False) -> dict:
    ticker = str(ticker).upper()
    job_id = uuid.uuid4().hex[:12]
    with _lock:
        _jobs[job_id] = {
            "job_id": job_id, "ticker": ticker, "status": "queued",
            "stage": "queued", "progress": 0, "message": "Queued",
            "error": None, "summary": None, "started_at": time.time(),
        }
    threading.Thread(target=_run, args=(job_id, ticker, force), daemon=True).start()
    return get_job(job_id)


def _run(job_id: str, ticker: str, force: bool) -> None:
    if not _run_lock.acquire(blocking=False):
        _set(job_id, message="Waiting for another company to finish processing…")
        _run_lock.acquire()  # block until the running job releases
    try:
        from pipeline.orchestrator import process_company
        _set(job_id, status="running", stage="starting", message="Starting…")

        def cb(stage, pct, message):
            _set(job_id, status="running", stage=stage, progress=pct, message=message)

        summary = process_company(ticker, progress_cb=cb, force=force)
        _set(job_id, status="done", stage="done", progress=100,
             message="Complete.", summary=summary)
    except Exception as e:  # surface the failure to the poller
        _set(job_id, status="error", message=str(e)[:300], error=str(e)[:300])
    finally:
        _run_lock.release()
