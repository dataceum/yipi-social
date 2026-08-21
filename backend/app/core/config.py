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

    # ------------------------------------------------------------------
    # Media storage (S3 + CloudFront) — see README.md "Secure Media File
    # Uploads" section for the intended architecture: the bucket blocks
    # all public access, CloudFront reaches it via an Origin Access
    # Control (OAC) policy, and this app only ever hands out short-lived
    # presigned PUT URLs so uploads never pass through the API process.
    # ------------------------------------------------------------------
    AWS_REGION: str = "us-east-1"
    S3_MEDIA_BUCKET: str = ""
    # CloudFront distribution domain (or custom domain behind it) fronting
    # S3_MEDIA_BUCKET, e.g. "media.yourdomain.com" — this is the FastAPI
    # equivalent of the AWS_S3_CUSTOM_DOMAIN setting noted in README.md.
    # Left blank, uploaded asset URLs fall back to the raw S3 URL, which is
    # only usable for local/dev buckets that still allow public reads.
    CLOUDFRONT_MEDIA_DOMAIN: str = ""
    MEDIA_UPLOAD_URL_EXPIRE_SECONDS: int = 300

    # Static credentials for LOCAL DEVELOPMENT ONLY. In ECS, leave these
    # unset — boto3's default credential chain picks up the task's IAM
    # role automatically, so no AWS keys ever need to live in the image,
    # the task definition, or this .env file in production.
    AWS_ACCESS_KEY_ID: str | None = None
    AWS_SECRET_ACCESS_KEY: str | None = None


# Create an instance of the Settings class to load the configuration
settings = Settings()
