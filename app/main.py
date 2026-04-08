import asyncio
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import api_router
from app.core.config import settings
from app.core.metrics import MetricsMiddleware, metrics_endpoint
from app.services.job_queue import refresh_queue_metrics
from app.services.rate_limiter import rate_limiter
from app.services.vllm_client import vllm_client

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


async def _queue_metrics_loop():
    """Background task: refresh queue-depth gauges every 15 seconds."""
    while True:
        try:
            refresh_queue_metrics()
        except Exception:
            pass  # Never crash the app over a metrics refresh
        await asyncio.sleep(15)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("Starting MaintServe", vllm_url=settings.vllm_base_url)

    # Startup: verify vLLM connection
    health = await vllm_client.health_check()
    if health.get("status") == "healthy":
        logger.info("vLLM backend connected")
    else:
        logger.warning("vLLM backend not available", health=health)

    # Start background queue-metrics refresh
    queue_task = asyncio.create_task(_queue_metrics_loop())

    yield

    # Shutdown: cleanup
    queue_task.cancel()
    logger.info("Shutting down MaintServe")
    await vllm_client.close()
    await rate_limiter.close()


app = FastAPI(
    title=settings.app_name,
    description="Internal Vision LLM API Gateway with monitoring and management",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure as needed for your internal network
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Metrics middleware
if settings.enable_metrics:
    app.add_middleware(MetricsMiddleware)
    app.add_api_route("/metrics", metrics_endpoint, methods=["GET"], include_in_schema=False)

# Include API routes
app.include_router(api_router, prefix=settings.api_prefix)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": settings.app_name,
        "version": "0.1.0",
        "docs": "/docs",
        "health": f"{settings.api_prefix}/health",
    }
