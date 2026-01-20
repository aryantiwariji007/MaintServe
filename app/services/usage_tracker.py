import uuid
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_key import APIKey
from app.models.usage_log import UsageLog
from app.models.user import User
from app.schemas.usage import UsageStats


class UsageTracker:
    """Service for tracking and querying API usage."""

    @staticmethod
    def generate_request_id() -> str:
        """Generate a unique request ID."""
        return f"req_{uuid.uuid4().hex[:16]}"

    @staticmethod
    async def log_request(
        db: AsyncSession,
        user_id: int,
        api_key_id: int,
        request_id: str,
        endpoint: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: float | None,
        status_code: int,
        error_message: str | None = None,
        client_ip: str | None = None,
    ) -> UsageLog:
        """Log an API request."""
        log = UsageLog(
            user_id=user_id,
            api_key_id=api_key_id,
            request_id=request_id,
            endpoint=endpoint,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            latency_ms=latency_ms,
            status_code=status_code,
            error_message=error_message,
            client_ip=client_ip,
        )
        db.add(log)
        await db.commit()
        await db.refresh(log)
        return log

    @staticmethod
    async def get_user_stats(
        db: AsyncSession,
        user_id: int,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> UsageStats:
        """Get usage statistics for a user."""
        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=30)
        if not end_date:
            end_date = datetime.utcnow()

        result = await db.execute(
            select(
                func.count(UsageLog.id).label("total_requests"),
                func.sum(UsageLog.total_tokens).label("total_tokens"),
                func.sum(UsageLog.prompt_tokens).label("total_prompt_tokens"),
                func.sum(UsageLog.completion_tokens).label("total_completion_tokens"),
                func.avg(UsageLog.latency_ms).label("avg_latency_ms"),
                func.sum(
                    func.cast(UsageLog.status_code >= 400, Integer)
                ).label("error_count"),
            )
            .where(UsageLog.user_id == user_id)
            .where(UsageLog.created_at >= start_date)
            .where(UsageLog.created_at <= end_date)
        )
        row = result.one()

        return UsageStats(
            total_requests=row.total_requests or 0,
            total_tokens=row.total_tokens or 0,
            total_prompt_tokens=row.total_prompt_tokens or 0,
            total_completion_tokens=row.total_completion_tokens or 0,
            avg_latency_ms=float(row.avg_latency_ms) if row.avg_latency_ms else None,
            error_count=row.error_count or 0,
            period_start=start_date,
            period_end=end_date,
        )

    @staticmethod
    async def get_daily_requests_count(
        db: AsyncSession,
        user_id: int,
    ) -> int:
        """Get today's request count for a user."""
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        result = await db.execute(
            select(func.count(UsageLog.id))
            .where(UsageLog.user_id == user_id)
            .where(UsageLog.created_at >= today_start)
        )
        return result.scalar() or 0

    @staticmethod
    async def get_monthly_tokens(
        db: AsyncSession,
        user_id: int,
    ) -> int:
        """Get this month's token usage for a user."""
        month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        result = await db.execute(
            select(func.sum(UsageLog.total_tokens))
            .where(UsageLog.user_id == user_id)
            .where(UsageLog.created_at >= month_start)
        )
        return result.scalar() or 0

    @staticmethod
    async def check_quota(
        db: AsyncSession,
        user: User,
    ) -> tuple[bool, str | None]:
        """
        Check if user is within quota.
        Returns (is_allowed, error_message).
        """
        # Check daily request limit
        if user.daily_request_limit:
            daily_count = await UsageTracker.get_daily_requests_count(db, user.id)
            if daily_count >= user.daily_request_limit:
                return False, f"Daily request limit ({user.daily_request_limit}) exceeded"

        # Check monthly token limit
        if user.monthly_token_limit:
            monthly_tokens = await UsageTracker.get_monthly_tokens(db, user.id)
            if monthly_tokens >= user.monthly_token_limit:
                return False, f"Monthly token limit ({user.monthly_token_limit}) exceeded"

        return True, None


# Need to import Integer for the cast
from sqlalchemy import Integer  # noqa: E402
