from typing import Any

from pydantic import BaseModel, Field

from app.core.config import settings


class ImageUrl(BaseModel):
    url: str  # Can be URL or base64 data URI


class ContentPart(BaseModel):
    type: str  # "text" or "image_url"
    text: str | None = None
    image_url: ImageUrl | None = None


class ChatMessage(BaseModel):
    role: str  # "system", "user", "assistant"
    content: str | list[ContentPart]


class ChatCompletionRequest(BaseModel):
    model: str = settings.default_model
    messages: list[ChatMessage]
    max_tokens: int | None = Field(default=2048, ge=1, le=16384)
    temperature: float | None = Field(default=0.7, ge=0, le=2)
    top_p: float | None = Field(default=1.0, ge=0, le=1)
    stream: bool = False
    stop: list[str] | None = None
    priority: str = Field(default="normal", description="Request priority: 'normal' or 'urgent'")

    # Additional vLLM/Ollama params
    presence_penalty: float | None = Field(default=0, ge=-2, le=2)
    frequency_penalty: float | None = Field(default=0, ge=-2, le=2)
    options: dict[str, Any] | None = Field(default=None, description="Backend specific options like num_ctx")


class Usage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class Choice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: str | None


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[Choice]
    usage: Usage

    # MaintServe additions
    request_id: str | None = None
    latency_ms: float | None = None
