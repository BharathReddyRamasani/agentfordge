"""Job queue: Redis-backed in thread/external modes, synchronous inline execution in
sync mode (used by tests). Bounded retries are enforced by the orchestrator, not the queue."""

import json
import time

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("agentforge.workers")
QUEUE_KEY = "agentforge:jobs"
_redis_client = None


def get_redis():
    """Return a Redis client, falling back to an in-process fake when Redis is unreachable."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    if settings.redis_url.startswith("fakeredis"):
        import fakeredis

        _redis_client = fakeredis.FakeStrictRedis(decode_responses=True)
        return _redis_client
    try:
        import redis as redis_lib

        client = redis_lib.Redis.from_url(
            settings.redis_url, decode_responses=True, socket_connect_timeout=3, socket_timeout=5
        )
        client.ping()
        _redis_client = client
        logger.info("Connected to Redis", extra={"event": "redis_connected"})
    except Exception as exc:
        import fakeredis

        logger.warning(
            "Redis unreachable, using in-process fallback",
            extra={"event": "redis_fallback", "error": str(exc)[:200]},
        )
        _redis_client = fakeredis.FakeStrictRedis(decode_responses=True)
    return _redis_client


class JobQueue:
    def __init__(self, client=None):
        self.client = client or get_redis()

    def enqueue(self, job: dict) -> dict:
        if settings.worker_mode == "sync":
            # Tests: execute inline in the requesting process for determinism
            from app.orchestrator.engine import WorkflowRunner

            WorkflowRunner().run_job(job)
            return {"mode": "sync", "job": job}
        self.client.rpush(QUEUE_KEY, json.dumps(job, default=str))
        return {"mode": settings.worker_mode, "job": job}

    def dequeue(self, timeout: float | None = None):
        timeout = settings.worker_poll_interval if timeout is None else timeout
        try:
            res = self.client.blpop(QUEUE_KEY, timeout=timeout)
        except Exception:
            time.sleep(0.5)
            return None
        if not res:
            return None
        return json.loads(res[1])

    def length(self) -> int:
        try:
            return int(self.client.llen(QUEUE_KEY))
        except Exception:
            return 0


_job_queue: JobQueue | None = None


def get_job_queue() -> JobQueue:
    global _job_queue
    if _job_queue is None:
        _job_queue = JobQueue()
    return _job_queue
