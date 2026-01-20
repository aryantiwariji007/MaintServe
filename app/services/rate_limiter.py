import time

import redis.asyncio as redis
import structlog

from app.core.config import settings

logger = structlog.get_logger()


class RateLimiter:
    """Redis-based rate limiter using sliding window."""

    def __init__(self):
        self._redis: redis.Redis | None = None

    async def get_redis(self) -> redis.Redis:
        if self._redis is None:
            self._redis = redis.from_url(settings.redis_url)
        return self._redis

    async def close(self):
        if self._redis:
            await self._redis.close()
            self._redis = None

    async def is_allowed(
        self,
        key: str,
        limit: int | None = None,
        window: int | None = None,
    ) -> tuple[bool, dict]:
        """
        Check if request is allowed under rate limit.

        Returns (is_allowed, info_dict) where info_dict contains:
        - remaining: requests remaining in window
        - reset: seconds until window resets
        - limit: the limit applied
        """
        limit = limit or settings.rate_limit_requests
        window = window or settings.rate_limit_window

        try:
            r = await self.get_redis()
            now = time.time()
            window_start = now - window

            # Use sorted set for sliding window
            rate_key = f"ratelimit:{key}"

            pipe = r.pipeline()
            # Remove old entries
            pipe.zremrangebyscore(rate_key, 0, window_start)
            # Count current entries
            pipe.zcard(rate_key)
            # Add current request
            pipe.zadd(rate_key, {str(now): now})
            # Set expiry
            pipe.expire(rate_key, window)

            results = await pipe.execute()
            current_count = results[1]

            is_allowed = current_count < limit
            remaining = max(0, limit - current_count - 1) if is_allowed else 0

            return is_allowed, {
                "remaining": remaining,
                "reset": window,
                "limit": limit,
            }

        except redis.RedisError as e:
            # If Redis fails, allow the request but log the error
            logger.warning("Rate limiter Redis error, allowing request", error=str(e))
            return True, {"remaining": -1, "reset": window, "limit": limit}

    async def get_usage(self, key: str, window: int | None = None) -> int:
        """Get current usage count for a key."""
        window = window or settings.rate_limit_window

        try:
            r = await self.get_redis()
            now = time.time()
            window_start = now - window
            rate_key = f"ratelimit:{key}"

            # Clean and count
            await r.zremrangebyscore(rate_key, 0, window_start)
            return await r.zcard(rate_key)

        except redis.RedisError:
            return 0


# Singleton instance
rate_limiter = RateLimiter()
