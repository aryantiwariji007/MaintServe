import secrets
from datetime import datetime

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.api_key import APIKey
from app.models.user import User

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


def generate_api_key() -> str:
    """Generate a secure random API key."""
    return f"ms_{secrets.token_urlsafe(32)}"


async def get_api_key(
    api_key: str | None = Security(API_KEY_HEADER),
    db: AsyncSession = Depends(get_db),
) -> APIKey:
    """Validate API key and return the key object."""
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
        )

    result = await db.execute(
        select(APIKey)
        .where(APIKey.key == api_key)
        .where(APIKey.is_active == True)  # noqa: E712
    )
    key_obj = result.scalar_one_or_none()

    if not key_obj:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    # Check expiration
    if key_obj.expires_at and key_obj.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key expired",
        )

    # Update last used
    key_obj.last_used_at = datetime.utcnow()
    await db.commit()

    return key_obj


async def get_current_user(
    api_key: APIKey = Depends(get_api_key),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Get the user associated with the API key."""
    result = await db.execute(select(User).where(User.id == api_key.user_id))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User inactive",
        )

    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    """Require admin privileges."""
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user
