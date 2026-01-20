from datetime import datetime

from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    name: str
    email: EmailStr
    team: str | None = None
    is_admin: bool = False
    daily_request_limit: int | None = None
    monthly_token_limit: int | None = None


class UserUpdate(BaseModel):
    name: str | None = None
    team: str | None = None
    is_active: bool | None = None
    is_admin: bool | None = None
    daily_request_limit: int | None = None
    monthly_token_limit: int | None = None


class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    team: str | None
    is_active: bool
    is_admin: bool
    daily_request_limit: int | None
    monthly_token_limit: int | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
