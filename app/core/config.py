from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Application
    app_name: str = "MaintServe"
    debug: bool = False
    api_prefix: str = "/api/v1"

    # vLLM Backend
    vllm_base_url: str = "http://localhost:8001"
    vllm_timeout: float = 300.0  # 5 minutes for long generations
    vllm_max_concurrency: int = 10  # Max simultaneous calls to backend
    default_model: str = "Qwen/Qwen3-VL-8B-Instruct"

    # Database
    database_url: str = "postgresql+asyncpg://maintserve:maintserve@localhost:5432/maintserve"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Rate Limiting
    rate_limit_requests: int = 100  # requests per window
    rate_limit_window: int = 60  # window in seconds

    # Admin
    admin_api_key: str = "admin-secret-key-change-me"

    # Metrics
    enable_metrics: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
