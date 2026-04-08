import asyncio
import time
from collections.abc import AsyncIterator
from typing import Any

import httpx
import structlog

from app.core.config import settings
from app.schemas.inference import ChatCompletionRequest, ChatCompletionResponse
from app.core.metrics import VLLM_CONCURRENCY_WAITING

logger = structlog.get_logger()


class VLLMClient:
    """Client for proxying requests to vLLM server."""

    def __init__(self):
        self.base_url = settings.vllm_base_url
        self.timeout = settings.vllm_timeout
        self._client: httpx.AsyncClient | None = None
        self._semaphore: asyncio.Semaphore | None = None

    def _get_semaphore(self) -> asyncio.Semaphore:
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(settings.vllm_max_concurrency)
        return self._semaphore

    async def get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(self.timeout, connect=10.0),
            )
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
        self._semaphore = None

    async def chat_completion(
        self, request: ChatCompletionRequest
    ) -> tuple[ChatCompletionResponse, float]:
        """
        Send chat completion request to vLLM.
        Returns (response, latency_ms).
        """
        sem = self._get_semaphore()
        VLLM_CONCURRENCY_WAITING.inc()
        
        async with sem:
            VLLM_CONCURRENCY_WAITING.dec()
            client = await self.get_client()

            # Convert to dict for vLLM
            payload = request.model_dump(exclude_none=True)
            
            # Remove MaintServe internal fields that vLLM doesn't understand
            payload.pop("priority", None)
            for key in list(payload.keys()):
                if key.startswith("_"):
                    payload.pop(key)
            
            # If 'options' exists, merge it into the root for Ollama/vLLM compatibility
            if "options" in payload and isinstance(payload["options"], dict):
                options = payload.pop("options")
                payload.update(options)

            # Ollama/vLLM vision fix: ensure images are in a top-level 'images' list
            if "images" not in payload:
                images = []
                for msg in payload.get("messages", []):
                    content = msg.get("content")
                    if isinstance(content, list):
                        for part in content:
                            if isinstance(part, dict) and part.get("type") == "image_url":
                                img_url = part.get("image_url", {}).get("url", "")
                                if img_url:
                                    images.append(img_url)
                if images:
                    payload["images"] = images

            logger.info("Sending request to vLLM", payload_keys=list(payload.keys()), num_images=len(payload.get("images", [])))
            
            start_time = time.perf_counter()

            try:
                response = await client.post(
                    "/v1/chat/completions",
                    json=payload,
                )
                response.raise_for_status()

                latency_ms = (time.perf_counter() - start_time) * 1000
                
                raw_text = response.text
                logger.debug("Received response from vLLM", status_code=response.status_code, text=raw_text[:200])
                
                data = response.json()

                return ChatCompletionResponse(**data), latency_ms

            except httpx.HTTPStatusError as e:
                logger.error(
                    "vLLM request failed",
                    status_code=e.response.status_code,
                    detail=e.response.text,
                )
                raise
            except httpx.RequestError as e:
                logger.error("vLLM connection error", error=str(e))
                raise

    async def chat_completion_stream(
        self, request: ChatCompletionRequest
    ) -> AsyncIterator[str]:
        """Stream chat completion from vLLM."""
        sem = self._get_semaphore()
        VLLM_CONCURRENCY_WAITING.inc()

        async with sem:
            VLLM_CONCURRENCY_WAITING.dec()
            client = await self.get_client()

            payload = request.model_dump(exclude_none=True)
            payload["stream"] = True

            # Remove MaintServe internal fields that vLLM doesn't understand
            payload.pop("priority", None)
            for key in list(payload.keys()):
                if key.startswith("_"):
                    payload.pop(key)
            
            # If 'options' exists, merge it into the root for Ollama/vLLM compatibility
            if "options" in payload and isinstance(payload["options"], dict):
                options = payload.pop("options")
                payload.update(options)

            async with client.stream(
                "POST",
                "/v1/chat/completions",
                json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        yield line + "\n\n"

    async def health_check(self) -> dict[str, Any]:
        """Check vLLM server health."""
        client = await self.get_client()
        try:
            response = await client.get("/health")
            return {"status": "healthy", "vllm_status": response.status_code}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    async def get_models(self) -> list[dict[str, Any]]:
        """Get available models from vLLM."""
        client = await self.get_client()
        response = await client.get("/v1/models")
        response.raise_for_status()
        return response.json().get("data", [])


# Singleton instance
vllm_client = VLLMClient()
