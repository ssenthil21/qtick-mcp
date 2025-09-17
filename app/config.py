from functools import lru_cache
from typing import List

from pydantic import AnyHttpUrl, BaseSettings, Field, validator


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    app_name: str = Field(default="QTick MCP Service", alias="APP_NAME")
    cors_origins: List[AnyHttpUrl] = Field(
        default_factory=lambda: [
            "http://localhost:5500",
            "http://127.0.0.1:5500",
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
        default="http://localhost:8000", alias="MCP_BASE_URL"
    )

    class Config:
        env_prefix = "QTICK_"
        case_sensitive = False

    @validator("cors_origins", pre=True)
    def _split_origins(cls, value):
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings."""

    return Settings()
