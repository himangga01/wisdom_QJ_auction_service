from functools import lru_cache
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

RuntimeMode = Literal["local", "docker"]
LOCAL_DATABASE_URL = "sqlite+aiosqlite:///./data/wisdom_local.db"
DOCKER_DATABASE_URL = (
    "postgresql+asyncpg://postgres:postgres@localhost:5432/wisdom_auction"
)
RUNTIME_CDP_ENDPOINTS: dict[RuntimeMode, str] = {
    "local": "http://127.0.0.1:42973",
    "docker": "http://chrome:9222",
}
BOOTSTRAP_TOKEN_PLACEHOLDERS = {
    "replace-with-at-least-32-random-bytes",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_runtime: RuntimeMode = "docker"
    database_url: str = ""
    redis_url: str = "redis://localhost:6379/0"
    crawler_cdp_url: str = ""
    crawl_concurrency: int = Field(default=1, ge=1)
    naver_request_delay_min: float = Field(default=1.0, ge=0)
    naver_request_delay_max: float = Field(default=2.5, ge=0)
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]
    timezone: str = "Asia/Seoul"
    auth_session_ttl_hours: int = Field(default=12, ge=1)
    auth_cookie_secure: bool = True
    auth_bootstrap_token: str = ""
    auth_allowed_origins: Annotated[list[str], NoDecode] = [
        "http://127.0.0.1:42880",
        "http://localhost:42880",
    ]

    @property
    def is_local(self) -> bool:
        return self.app_runtime == "local"

    @field_validator("cors_origins", "auth_allowed_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("auth_bootstrap_token")
    @classmethod
    def validate_bootstrap_token(cls, value: str) -> str:
        token = value.strip()
        if not token:
            return ""
        if len(token) < 32 or token in BOOTSTRAP_TOKEN_PLACEHOLDERS:
            raise ValueError(
                "AUTH_BOOTSTRAP_TOKEN must be a non-placeholder token "
                "with at least 32 characters"
            )
        return token

    @model_validator(mode="after")
    def configure_runtime(self) -> "Settings":
        if not self.database_url:
            self.database_url = (
                LOCAL_DATABASE_URL if self.is_local else DOCKER_DATABASE_URL
            )

        expected_endpoint = RUNTIME_CDP_ENDPOINTS[self.app_runtime]
        if not self.crawler_cdp_url:
            self.crawler_cdp_url = expected_endpoint
        try:
            parsed = urlsplit(self.crawler_cdp_url)
            port = parsed.port
        except ValueError as exc:
            raise ValueError(
                "CRAWLER_CDP_URL must match the APP_RUNTIME Chrome endpoint"
            ) from exc

        expected = urlsplit(expected_endpoint)
        if (
            parsed.scheme != "http"
            or parsed.hostname != expected.hostname
            or port != expected.port
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in ("", "/")
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError(
                "CRAWLER_CDP_URL must match the APP_RUNTIME Chrome endpoint"
            )
        if self.naver_request_delay_max < self.naver_request_delay_min:
            raise ValueError("NAVER_REQUEST_DELAY_MAX must be >= NAVER_REQUEST_DELAY_MIN")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
