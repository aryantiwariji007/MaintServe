from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_api_key, get_current_user
from app.models.api_key import APIKey
from app.models.user import User
from app.schemas.inference import ChatCompletionRequest, ChatCompletionResponse
from app.services.rate_limiter import rate_limiter
from app.services.usage_tracker import UsageTracker
from app.services.vllm_client import vllm_client

router = APIRouter()


@router.post("/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(
    request_body: ChatCompletionRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    api_key: APIKey = Depends(get_api_key),
    user: User = Depends(get_current_user),
):
    """
    OpenAI-compatible chat completions endpoint.
    Proxies requests to vLLM backend with authentication, rate limiting, and logging.
    """
    request_id = UsageTracker.generate_request_id()

    # Check rate limit
    is_allowed, rate_info = await rate_limiter.is_allowed(f"user:{user.id}")
    if not is_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={
                "X-RateLimit-Limit": str(rate_info["limit"]),
                "X-RateLimit-Remaining": str(rate_info["remaining"]),
                "X-RateLimit-Reset": str(rate_info["reset"]),
            },
        )

    # Check quota
    quota_ok, quota_error = await UsageTracker.check_quota(db, user)
    if not quota_ok:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=quota_error,
        )

    # Handle streaming
    if request_body.stream:
        return StreamingResponse(
            stream_with_logging(request_body, user, api_key, request_id, db, request),
            media_type="text/event-stream",
            headers={
                "X-Request-ID": request_id,
                "Cache-Control": "no-cache",
            },
        )

    # Non-streaming request
    try:
        response, latency_ms = await vllm_client.chat_completion(request_body)

        # Add MaintServe metadata
        response.request_id = request_id
        response.latency_ms = latency_ms

        # Log usage
        await UsageTracker.log_request(
            db=db,
            user_id=user.id,
            api_key_id=api_key.id,
            request_id=request_id,
            endpoint="/v1/chat/completions",
            model=request_body.model,
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
            latency_ms=latency_ms,
            status_code=200,
            client_ip=request.client.host if request.client else None,
        )

        return response

    except Exception as e:
        # Log error
        await UsageTracker.log_request(
            db=db,
            user_id=user.id,
            api_key_id=api_key.id,
            request_id=request_id,
            endpoint="/v1/chat/completions",
            model=request_body.model,
            prompt_tokens=0,
            completion_tokens=0,
            latency_ms=None,
            status_code=500,
            error_message=str(e),
            client_ip=request.client.host if request.client else None,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"vLLM backend error: {str(e)}",
        )


async def stream_with_logging(
    request_body: ChatCompletionRequest,
    user: User,
    api_key: APIKey,
    request_id: str,
    db: AsyncSession,
    request: Request,
):
    """Stream response and log usage after completion."""
    total_tokens = 0

    try:
        async for chunk in vllm_client.chat_completion_stream(request_body):
            yield chunk
            # Note: Token counting in streaming is approximate
            # vLLM sends token counts in final chunk

    except Exception as e:
        await UsageTracker.log_request(
            db=db,
            user_id=user.id,
            api_key_id=api_key.id,
            request_id=request_id,
            endpoint="/v1/chat/completions",
            model=request_body.model,
            prompt_tokens=0,
            completion_tokens=0,
            latency_ms=None,
            status_code=500,
            error_message=str(e),
            client_ip=request.client.host if request.client else None,
        )
        raise

    # Log successful streaming request
    # Note: Exact token counts unavailable for streaming; would need to parse final chunk
    await UsageTracker.log_request(
        db=db,
        user_id=user.id,
        api_key_id=api_key.id,
        request_id=request_id,
        endpoint="/v1/chat/completions",
        model=request_body.model,
        prompt_tokens=0,  # Would need parsing
        completion_tokens=0,
        latency_ms=None,
        status_code=200,
        client_ip=request.client.host if request.client else None,
    )
