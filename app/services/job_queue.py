import redis
from rq import Queue
from rq.job import Job

from app.core.config import settings

# Redis connection for RQ
redis_conn = redis.from_url(settings.redis_url)

# Job queues with different priorities
inference_queue = Queue("inference", connection=redis_conn, default_timeout=600)  # 10 min timeout
high_priority_queue = Queue("high", connection=redis_conn, default_timeout=300)


def enqueue_inference_job(request_data: dict, high_priority: bool = False) -> str:
    """Enqueue an inference job and return the job ID."""
    queue = high_priority_queue if high_priority else inference_queue

    job = queue.enqueue(
        "app.workers.inference_worker.process_inference",
        request_data,
        job_timeout=600,
        result_ttl=3600,  # Keep result for 1 hour
        failure_ttl=86400,  # Keep failed jobs for 24 hours
    )
    return job.id


def get_job(job_id: str) -> Job | None:
    """Get a job by ID."""
    try:
        return Job.fetch(job_id, connection=redis_conn)
    except Exception:
        return None


def get_job_status(job_id: str) -> dict:
    """Get job status and result if available."""
    job = get_job(job_id)

    if not job:
        return {"status": "not_found", "job_id": job_id}

    status = job.get_status()
    result = {
        "job_id": job_id,
        "status": status,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "ended_at": job.ended_at.isoformat() if job.ended_at else None,
    }

    if status == "finished":
        result["result"] = job.result
    elif status == "failed":
        result["error"] = str(job.exc_info) if job.exc_info else "Unknown error"
    elif status == "started":
        result["progress"] = job.meta.get("progress", 0)

    return result


def get_queue_stats() -> dict:
    """Get queue statistics."""
    return {
        "inference": {
            "queued": len(inference_queue),
            "started": inference_queue.started_job_registry.count,
            "finished": inference_queue.finished_job_registry.count,
            "failed": inference_queue.failed_job_registry.count,
        },
        "high_priority": {
            "queued": len(high_priority_queue),
            "started": high_priority_queue.started_job_registry.count,
            "finished": high_priority_queue.finished_job_registry.count,
            "failed": high_priority_queue.failed_job_registry.count,
        },
    }
