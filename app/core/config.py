from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Project Settings
    PROJECT_NAME: str = "AI Agents Data API"
    API_V1_STR: str = "/api/v1"

    # API Settings
    API_VERSION: str
    DEBUG: bool = False
    ENVIRONMENT: str
    SECRET_KEY: str
    ADMIN_TOKEN: str
    ADMIN_USERNAME: str
    ADMIN_PASSWORD: str

    # Database Settings
    DUCKDB_PATH: str

    # Snowflake Settings
    SNOWFLAKE_ACCOUNT: str
    SNOWFLAKE_USER: str
    SNOWFLAKE_PASSWORD: str
    SNOWFLAKE_WAREHOUSE: str
    SNOWFLAKE_DATABASE: str
    SNOWFLAKE_SCHEMA: str

    # Token Settings
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Artifact Settings
    ARTIFACT_MAX_SIZE_MB: int = 50
    ARTIFACT_EXPIRY_DAYS: int = 10

    # Server Settings
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Redis Settings
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379

    # Celery Settings
    CELERY_BROKER_URL: str = "redis://redis:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/1"
    CELERY_WORKER_CONCURRENCY: int = 2
    CELERY_TASK_TRACK_STARTED: bool = True
    CELERY_TASK_TIME_LIMIT: int = 3600  # 1 hour
    CELERY_TASK_SOFT_TIME_LIMIT: int = 3300  # 55 minutes

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )


settings = Settings() 