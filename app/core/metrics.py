from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Request, Response
from fastapi.routing import APIRoute
from starlette.middleware.base import BaseHTTPMiddleware
import time

# Metrics
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


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to collect request metrics."""

    async def dispatch(self, request: Request, call_next):
        # Skip metrics endpoint to avoid recursion
        if request.url.path == "/metrics":
            return await call_next(request)

        ACTIVE_REQUESTS.inc()
        start_time = time.perf_counter()

        try:
            response = await call_next(request)

            # Record metrics
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

            return response

        finally:
            ACTIVE_REQUESTS.dec()

    def _get_endpoint(self, request: Request) -> str:
        """Get a normalized endpoint path for metrics."""
        # Use route path if available, otherwise use the actual path
        if request.scope.get("route"):
            return request.scope["route"].path
        return request.url.path


def record_tokens(prompt_tokens: int, completion_tokens: int):
    """Record token usage in metrics."""
    TOKENS_TOTAL.labels(type="prompt").inc(prompt_tokens)
    TOKENS_TOTAL.labels(type="completion").inc(completion_tokens)


async def metrics_endpoint():
    """Prometheus metrics endpoint."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
