import os
from functools import lru_cache
from typing import List

from pydantic import AnyHttpUrl, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def runtime_default_mcp_base_url() -> str:
    """Return the default MCP base URL based on the runtime environment."""

    render_url = os.getenv("RENDER_EXTERNAL_URL")
    if render_url:
        return render_url.rstrip("/")

    port = os.getenv("PORT")
    if port:
        host = os.getenv("QTICK_RUNTIME_HOST", "127.0.0.1")
        scheme = os.getenv("QTICK_RUNTIME_SCHEME", "http")
        return f"{scheme}://{host}:{port}".rstrip("/")

    return "http://localhost:8000"


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    app_name: str = Field(default="QTick MCP Service", alias="APP_NAME")
    cors_origins: List[AnyHttpUrl] = Field(
        default_factory=lambda: [
            "http://localhost:5500",
            "http://127.0.0.1:5500",
            "http://localhost:2500",
            "http://127.0.0.1:2500",
        ]
    )
    java_service_base_url: AnyHttpUrl | None = Field(
        default=None, alias="JAVA_SERVICE_BASE_URL"
    )
    java_service_timeout: float = Field(default=10.0, alias="JAVA_SERVICE_TIMEOUT")
    use_mock_data: bool = Field(default=True, alias="USE_MOCK_DATA")
    google_api_key: str | None = Field(default=None, alias="GOOGLE_API_KEY")
    agent_google_model: str = Field(default="gemini-1.5-flash", alias="AGENT_GOOGLE_MODEL")
    agent_temperature: float = Field(default=0.0, alias="AGENT_TEMPERATURE")
    mcp_base_url: AnyHttpUrl = Field(
        default_factory=runtime_default_mcp_base_url, alias="MCP_BASE_URL"
    )

    model_config = SettingsConfigDict(env_prefix="QTICK_", case_sensitive=False)

    @field_validator("cors_origins", mode="before")
    def _split_origins(cls, value):
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings."""

    return Settings()
