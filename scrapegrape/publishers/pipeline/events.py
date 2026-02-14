"""Redis pub/sub event publishing for pipeline progress."""

import json
import os

import redis
from loguru import logger


def get_redis_client():
    """Get a synchronous Redis client (for use in RQ workers)."""
    host = os.environ.get("REDIS_HOST", "localhost")
    port = int(os.environ.get("REDIS_PORT", 6379))
    return redis.Redis(host=host, port=port, db=0)


def publish_step_event(
    job_id: str, step: str, status: str, data: dict | None = None
):
    """Publish a pipeline step event to the job's Redis channel.

    Non-critical: failures are logged but do not crash the pipeline.

    Args:
        job_id: The ResolutionJob UUID string.
        step: Step name (e.g. "waf", "tos_discovery", "pipeline").
        status: One of "started", "completed", "failed", "skipped".
        data: Optional dict of step-specific data to include.
    """
    try:
        r = get_redis_client()
        event = {
            "step": step,
            "status": status,
            "data": data or {},
        }
        r.publish(f"job:{job_id}:events", json.dumps(event))
    except Exception as exc:
        logger.warning(f"Failed to publish event for job {job_id}: {exc}")
