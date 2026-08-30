"""Configuration settings for MPLAD FraudShield."""
import os
from typing import List

try:
    from pydantic_settings import BaseSettings
    from pydantic import field_validator
except ImportError:
    try:
        from pydantic import BaseSettings
        field_validator = None
    except ImportError:
        class BaseSettings:
            pass
        field_validator = None


def _parse_cors_origins() -> List[str]:
    """Parse CORS origins from environment. Supports comma-separated list."""
    env_origins = os.getenv("CORS_ORIGINS", "")
    if env_origins:
        return [o.strip() for o in env_origins.split(",") if o.strip()]

    app_env = os.getenv("APP_ENV", "development")
    if app_env == "production":
        # In production allow all origins (Vercel URLs change per deployment)
        return ["*"]

    return [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ]


class Settings(BaseSettings):
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./mplad_demo.db")
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    secret_key: str = os.getenv("SECRET_KEY", "changeme-in-production")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    google_api_key: str = os.getenv("GOOGLE_API_KEY", os.getenv("GEMINI_API_KEY", ""))
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", os.getenv("GOOGLE_API_KEY", ""))
    app_env: str = os.getenv("APP_ENV", "development")
    debug: bool = True
    cors_origins: List[str] = _parse_cors_origins()

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    if field_validator is not None:
        @field_validator("debug", mode="before")
        @classmethod
        def parse_debug(cls, value):
            if isinstance(value, str):
                normalized = value.strip().lower()
                if normalized in {"release", "prod", "production", "false", "0", "no", "off"}:
                    return False
                if normalized in {"dev", "development", "true", "1", "yes", "on"}:
                    return True
            return value


settings = Settings()

