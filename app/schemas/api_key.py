from datetime import datetime, timezone

from pydantic import BaseModel, field_validator


class APIKeyCreate(BaseModel):
    name: str
    description: str | None = None
    expires_at: datetime | None = None

    @field_validator("expires_at", mode="after")
    @classmethod
    def strip_timezone(cls, v):
        if isinstance(v, datetime) and v.tzinfo is not None:
            return v.astimezone(timezone.utc).replace(tzinfo=None)
        return v


class APIKeyUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None


class APIKeyResponse(BaseModel):
    id: int
    user_id: int
    name: str
    description: str | None
    is_active: bool
    expires_at: datetime | None
    last_used_at: datetime | None
    created_at: datetime
    # Note: key is only returned on creation
    key: str | None = None

    model_config = {"from_attributes": True}
