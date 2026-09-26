from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    github_token: SecretStr | None = None
    github_webhook_secret: SecretStr | None = None
    aws_region: str = "us-east-1"
    bedrock_model_id: str = "example-model-id"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
