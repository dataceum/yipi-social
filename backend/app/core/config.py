"""
Configuration settings for the application using Pydantic's BaseSettings.
This module defines a Settings class that reads configuration values from environment variables or a .env file. The settings include database connection details, security configurations, and CORS allowed origins. The settings instance is created to be used throughout the application for accessing these configuration values.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import List


class Settings(BaseSettings):
    # Tell Pydantic to read from the .env file
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    APP_TITLE: str
    APP_VERSION: str
    APP_DESCRIPTION: str

    # Database Connection
    DATABASE_URL: str

    # Code Environment
    ENVIRONMENT: str

    # Security Configuration
    SECRET_KEY: str
    ALGORITHM: str = "HS256"

    THREE_CX_TIMEZONE: str = "Africa/Accra"

    # CORS Allowed Origins
    CORS_ALLOWED_ORIGINS: List[str] = []

    @field_validator("CORS_ALLOWED_ORIGINS", mode="before")
    def split_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v


# Create an instance of the Settings class to load the configuration
settings = Settings()
