from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import generate_api_key, get_current_user, require_admin
from app.models.api_key import APIKey
from app.models.usage_log import UsageLog
from app.models.user import User
from app.schemas.api_key import APIKeyCreate, APIKeyResponse, APIKeyUpdate
from app.schemas.usage import UsageLogResponse, UsageStats
from app.schemas.user import UserCreate, UserResponse, UserUpdate
from app.services.usage_tracker import UsageTracker

router = APIRouter()


# ============== User Management ==============


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Create a new user."""
    # Check if email exists
    result = await db.execute(select(User).where(User.email == user_data.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    user = User(**user_data.model_dump())
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    """List all users."""
    result = await db.execute(select(User).offset(skip).limit(limit))
    return result.scalars().all()


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Get a specific user."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.patch("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Update a user."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    update_data = user_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)

    await db.commit()
    await db.refresh(user)
    return user


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Delete a user."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    await db.delete(user)
    await db.commit()


# ============== API Key Management ==============


@router.post("/users/{user_id}/keys", response_model=APIKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    user_id: int,
    key_data: APIKeyCreate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Create a new API key for a user."""
    # Verify user exists
    result = await db.execute(select(User).where(User.id == user_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="User not found")

    key = generate_api_key()
    api_key = APIKey(
        user_id=user_id,
        key=key,
        **key_data.model_dump(),
    )
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)

    # Return with the actual key (only shown once)
    response = APIKeyResponse.model_validate(api_key)
    response.key = key
    return response


@router.get("/users/{user_id}/keys", response_model=list[APIKeyResponse])
async def list_user_api_keys(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """List all API keys for a user."""
    result = await db.execute(select(APIKey).where(APIKey.user_id == user_id))
    keys = result.scalars().all()
    # Don't return the actual key values
    return [APIKeyResponse.model_validate(k) for k in keys]


@router.patch("/keys/{key_id}", response_model=APIKeyResponse)
async def update_api_key(
    key_id: int,
    key_data: APIKeyUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Update an API key."""
    result = await db.execute(select(APIKey).where(APIKey.id == key_id))
    api_key = result.scalar_one_or_none()
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    update_data = key_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(api_key, field, value)

    await db.commit()
    await db.refresh(api_key)
    return APIKeyResponse.model_validate(api_key)


@router.delete("/keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    key_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Revoke (delete) an API key."""
    result = await db.execute(select(APIKey).where(APIKey.id == key_id))
    api_key = result.scalar_one_or_none()
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    await db.delete(api_key)
    await db.commit()


# ============== Usage & Stats ==============


@router.get("/users/{user_id}/usage", response_model=UsageStats)
async def get_user_usage(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
    start_date: datetime | None = None,
    end_date: datetime | None = None,
):
    """Get usage statistics for a user."""
    return await UsageTracker.get_user_stats(db, user_id, start_date, end_date)


@router.get("/usage/logs", response_model=list[UsageLogResponse])
async def list_usage_logs(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
    user_id: int | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    """List usage logs with optional filtering."""
    query = select(UsageLog).order_by(UsageLog.created_at.desc())

    if user_id:
        query = query.where(UsageLog.user_id == user_id)

    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


# ============== Self-service endpoints ==============


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    user: User = Depends(get_current_user),
):
    """Get current user's info."""
    return user


@router.get("/me/usage", response_model=UsageStats)
async def get_my_usage(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    start_date: datetime | None = None,
    end_date: datetime | None = None,
):
    """Get current user's usage statistics."""
    return await UsageTracker.get_user_stats(db, user.id, start_date, end_date)


@router.get("/me/keys", response_model=list[APIKeyResponse])
async def get_my_keys(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get current user's API keys."""
    result = await db.execute(select(APIKey).where(APIKey.user_id == user.id))
    keys = result.scalars().all()
    return [APIKeyResponse.model_validate(k) for k in keys]
