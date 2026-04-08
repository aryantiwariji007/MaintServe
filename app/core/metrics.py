import uuid

import structlog
from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import time

logger = structlog.get_logger()

# --- Existing metrics ---

REQUEST_COUNT = Counter(
    "maintserve_requests_total",
    "Total number of requests",
    ["method", "endpoint", "status_code"],
)

REQUEST_LATENCY = Histogram(
    "maintserve_request_latency_seconds",
    "Request latency in seconds",
    ["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0],
)

TOKENS_TOTAL = Counter(
    "maintserve_tokens_total",
    "Total tokens processed",
    ["type"],  # prompt, completion
)

ACTIVE_REQUESTS = Gauge(
    "maintserve_active_requests",
    "Number of currently active requests",
)

VLLM_HEALTH = Gauge(
    "maintserve_vllm_healthy",
    "vLLM backend health status (1=healthy, 0=unhealthy)",
)

VLLM_CONCURRENCY_WAITING = Gauge(
    "maintserve_vllm_waiting_requests",
    "Number of requests waiting for a vLLM processing slot",
)

# --- Team-level usage metrics (high-level, not per-call) ---

TEAM_REQUESTS = Counter(
    "maintserve_team_requests_total",
    "Total requests by team",
    ["team", "status_code"],
)

TEAM_TOKENS = Counter(
    "maintserve_team_tokens_total",
    "Total tokens by team and type",
    ["team", "type"],  # type: prompt, completion
)

# --- Queue / load management metrics ---

QUEUE_DEPTH = Gauge(
    "maintserve_queue_depth",
    "Current job count in each queue by state",
    ["queue", "state"],  # queue: normal|urgent, state: queued|started|failed
)

JOBS_ENQUEUED = Counter(
    "maintserve_jobs_enqueued_total",
    "Total async jobs submitted by priority",
    ["priority"],  # normal, urgent
)


# --- Helper functions ---

def record_team_usage(team: str, prompt_tokens: int, completion_tokens: int, status_code: int):
    """Record team-level token and request metrics. Call after a completed inference."""
    label = team or "unknown"
    TEAM_REQUESTS.labels(team=label, status_code=str(status_code)).inc()
    TEAM_TOKENS.labels(team=label, type="prompt").inc(prompt_tokens)
    TEAM_TOKENS.labels(team=label, type="completion").inc(completion_tokens)


def record_tokens(prompt_tokens: int, completion_tokens: int):
    """Record token usage in global (non-team) metrics."""
    TOKENS_TOTAL.labels(type="prompt").inc(prompt_tokens)
    TOKENS_TOTAL.labels(type="completion").inc(completion_tokens)


# --- Middleware ---

class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to collect request metrics and propagate trace IDs."""

    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/metrics":
            return await call_next(request)

        # Generate a trace ID for every request and attach to request state
        trace_id = str(uuid.uuid4())
        request.state.trace_id = trace_id

        ACTIVE_REQUESTS.inc()
        start_time = time.perf_counter()

        try:
            response = await call_next(request)

            duration = time.perf_counter() - start_time
            endpoint = self._get_endpoint(request)

            REQUEST_COUNT.labels(
                method=request.method,
                endpoint=endpoint,
                status_code=response.status_code,
            ).inc()

            REQUEST_LATENCY.labels(
                method=request.method,
                endpoint=endpoint,
            ).observe(duration)

            # Surface trace ID on every response so callers can correlate logs
            response.headers["X-Trace-ID"] = trace_id

            logger.info(
                "request_completed",
                trace_id=trace_id,
                method=request.method,
                endpoint=endpoint,
                status_code=response.status_code,
                duration_ms=round(duration * 1000, 2),
            )

            return response

        finally:
            ACTIVE_REQUESTS.dec()

    def _get_endpoint(self, request: Request) -> str:
        if request.scope.get("route"):
            return request.scope["route"].path
        return request.url.path


async def metrics_endpoint():
    """Prometheus metrics endpoint."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
