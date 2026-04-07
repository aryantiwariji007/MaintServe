"""
MaintServe Python Client

Simple client for interacting with MaintServe API gateway.
Compatible with OpenAI SDK since MaintServe exposes OpenAI-compatible endpoints.
"""

import base64
import os
from pathlib import Path

import httpx

# Change this or set DEFAULT_MODEL env var to switch models globally
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "qwen2-vl:2b")


class MaintServeClient:
    """Client for MaintServe Vision LLM API Gateway."""

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_key: str | None = None,
        timeout: float = 300.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._client: httpx.Client | None = None

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            headers = {}
            if self.api_key:
                headers["X-API-Key"] = self.api_key
            self._client = httpx.Client(
                base_url=self.base_url,
                headers=headers,
                timeout=self.timeout,
            )
        return self._client

    def close(self):
        if self._client:
            self._client.close()
            self._client = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def chat(
        self,
        messages: list[dict],
        model: str = DEFAULT_MODEL,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        **kwargs,
    ) -> dict:
        """Send a chat completion request."""
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            **kwargs,
        }
        response = self.client.post("/api/v1/v1/chat/completions", json=payload)
        response.raise_for_status()
        return response.json()

    def chat_with_image(
        self,
        prompt: str,
        image_path: str | None = None,
        image_url: str | None = None,
        image_base64: str | None = None,
        **kwargs,
    ) -> dict:
        """Send a chat request with an image."""
        # Build image content
        if image_path:
            path = Path(image_path)
            with open(path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode()
            # Detect mime type
            suffix = path.suffix.lower()
            mime_types = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp"}
            mime_type = mime_types.get(suffix, "image/png")
            image_url = f"data:{mime_type};base64,{image_data}"
        elif image_base64:
            image_url = f"data:image/png;base64,{image_base64}"
        elif not image_url:
            raise ValueError("Must provide image_path, image_url, or image_base64")

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": image_url}},
                    {"type": "text", "text": prompt},
                ],
            }
        ]

        return self.chat(messages, **kwargs)

    def health(self) -> dict:
        """Check API health."""
        response = self.client.get("/api/v1/health")
        response.raise_for_status()
        return response.json()

    def health_detailed(self) -> dict:
        """Get detailed health status."""
        response = self.client.get("/api/v1/health/detailed")
        response.raise_for_status()
        return response.json()

    def get_usage(self) -> dict:
        """Get current user's usage statistics."""
        response = self.client.get("/api/v1/admin/me/usage")
        response.raise_for_status()
        return response.json()


# Example usage with OpenAI SDK (alternative)
def openai_example():
    """Example using OpenAI SDK with MaintServe."""
    from openai import OpenAI

    client = OpenAI(
        base_url="http://localhost:8000/api/v1/v1",
        api_key="your-maintserve-api-key",
        default_headers={"X-API-Key": "your-maintserve-api-key"},
    )

    response = client.chat.completions.create(
        model="Qwen/Qwen3-VL-8B-Instruct",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": "https://example.com/image.jpg"}},
                    {"type": "text", "text": "What's in this image?"},
                ],
            }
        ],
        max_tokens=2048,
    )

    print(response.choices[0].message.content)


if __name__ == "__main__":
    # Example usage
    client = MaintServeClient(
        base_url="http://localhost:8000",
        api_key="ms_admin_default_key_change_me",
    )

    # Health check
    print("Health:", client.health())

    # Simple text chat
    response = client.chat(
        messages=[{"role": "user", "content": "Hello! What can you help me with?"}]
    )
    print("Response:", response["choices"][0]["message"]["content"])
