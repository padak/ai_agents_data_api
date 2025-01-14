from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # API Settings
    API_VERSION: str
    DEBUG: bool = False
    ENVIRONMENT: str
    SECRET_KEY: str
    ADMIN_TOKEN: str

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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )


settings = Settings() 