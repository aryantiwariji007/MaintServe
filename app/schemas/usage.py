from datetime import datetime

from pydantic import BaseModel


class UsageLogResponse(BaseModel):
    id: int
    user_id: int
    request_id: str
    endpoint: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: float | None
    status_code: int
    error_message: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class UsageStats(BaseModel):
    total_requests: int
    total_tokens: int
    total_prompt_tokens: int
    total_completion_tokens: int
    avg_latency_ms: float | None
    error_count: int
    period_start: datetime
    period_end: datetime


class UserUsageSummary(BaseModel):
    user_id: int
    user_name: str
    total_requests: int
    total_tokens: int
    last_request_at: datetime | None
