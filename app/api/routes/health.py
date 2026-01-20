from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.rate_limiter import rate_limiter
from app.services.vllm_client import vllm_client

router = APIRouter()


@router.get("")
async def health_check():
    """Basic health check."""
    return {"status": "healthy"}


@router.get("/detailed")
async def detailed_health_check(db: AsyncSession = Depends(get_db)):
    """Detailed health check including all dependencies."""
    health = {
        "status": "healthy",
        "components": {},
    }

    # Check database
    try:
        await db.execute(text("SELECT 1"))
        health["components"]["database"] = {"status": "healthy"}
    except Exception as e:
        health["components"]["database"] = {"status": "unhealthy", "error": str(e)}
        health["status"] = "degraded"

    # Check Redis
    try:
        r = await rate_limiter.get_redis()
        await r.ping()
        health["components"]["redis"] = {"status": "healthy"}
    except Exception as e:
        health["components"]["redis"] = {"status": "unhealthy", "error": str(e)}
        health["status"] = "degraded"

    # Check vLLM
    vllm_health = await vllm_client.health_check()
    health["components"]["vllm"] = vllm_health
    if vllm_health.get("status") != "healthy":
        health["status"] = "degraded"

    return health


@router.get("/models")
async def list_models():
    """List available models from vLLM backend."""
    models = await vllm_client.get_models()
    return {"models": models}
