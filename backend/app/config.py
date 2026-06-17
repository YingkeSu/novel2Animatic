"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://novel2animatic:novel2animatic@localhost:5432/novel2animatic"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # StepFun
    STEPFUN_API_KEY: str = "IOz7U4ygRrjd83fXPwuiNsQLvnbgJkmcankAKfVEKh43ODRT1oJctdJ3M6OkMEOE"
    STEPFUN_BASE_URL: str = "https://api.stepfun.com/step_plan/v1"

    # Auth
    SECRET_KEY: str = "your-secret-key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15


@lru_cache
def get_settings() -> Settings:
    return Settings()
