"""Standalone worker process (docker-compose `worker` service) and the in-process
worker thread (local development). Both consume jobs from the same queue."""

import threading
import time

from app.core.logging import get_logger, setup_logging
from app.orchestrator.engine import WorkflowRunner
from app.workers.queue import JobQueue

logger = get_logger("agentforge.worker")


def run_worker_loop(once: bool = False, stop_event: threading.Event | None = None) -> None:
    queue = JobQueue()
    runner = WorkflowRunner()
    logger.info("Worker loop started", extra={"event": "worker_started"})
    while True:
        if stop_event is not None and stop_event.is_set():
            logger.info("Worker loop stopping", extra={"event": "worker_stopping"})
            break
        try:
            job = queue.dequeue()
        except Exception as exc:
            logger.error("queue error", extra={"event": "queue_error", "error": str(exc)[:300]})
            time.sleep(2.0)
            continue
        if job is None:
            if once:
                break
            time.sleep(0.5)
            continue
        try:
            runner.run_job(job)
        except Exception:
            logger.exception("job execution crashed", extra={"event": "job_crash"})
        if once:
            break


_worker_thread: threading.Thread | None = None
_worker_stop: threading.Event | None = None


def start_inprocess_worker() -> threading.Thread:
    """Start a daemon worker thread inside the FastAPI process (local dev default)."""
    global _worker_thread, _worker_stop
    if _worker_thread is not None and _worker_thread.is_alive():
        return _worker_thread
    _worker_stop = threading.Event()
    _worker_thread = threading.Thread(target=run_worker_loop, kwargs={"once": False, "stop_event": _worker_stop}, daemon=True, name="agentforge-worker")
    _worker_thread.start()
    return _worker_thread


def stop_inprocess_worker(timeout: float = 5.0) -> None:
    """Signal the in-process worker to stop (graceful shutdown)."""
    global _worker_thread, _worker_stop
    if _worker_stop is not None:
        _worker_stop.set()
    if _worker_thread is not None and _worker_thread.is_alive():
        _worker_thread.join(timeout=timeout)
    _worker_thread = None
    _worker_stop = None


if __name__ == "__main__":
    setup_logging()
    run_worker_loop()
