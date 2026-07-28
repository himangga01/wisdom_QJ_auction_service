from functools import lru_cache
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

RuntimeMode = Literal["local", "docker"]
BrowserMode = Literal["external_chrome", "playwright"]
LOCAL_DATABASE_URL = "sqlite+aiosqlite:///./data/wisdom_local.db"
DOCKER_DATABASE_URL = (
    "postgresql+asyncpg://postgres:postgres@localhost:5432/wisdom_auction"
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_runtime: RuntimeMode = "docker"
    database_url: str = ""
    redis_url: str = "redis://localhost:6379/0"
    crawler_headless: bool = True
    crawler_browser_mode: BrowserMode = "playwright"
    crawler_cdp_url: str = "http://127.0.0.1:42973"
    crawl_concurrency: int = Field(default=1, ge=1)
    naver_request_delay_min: float = Field(default=1.0, ge=0)
    naver_request_delay_max: float = Field(default=2.5, ge=0)
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]
    timezone: str = "Asia/Seoul"

    @property
    def is_local(self) -> bool:
        return self.app_runtime == "local"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("crawler_cdp_url")
    @classmethod
    def validate_crawler_cdp_url(cls, value: str) -> str:
        try:
            parsed = urlsplit(value)
            port = parsed.port
        except ValueError as exc:
            raise ValueError("CRAWLER_CDP_URL must use a valid explicit port") from exc

        if (
            parsed.scheme != "http"
            or parsed.hostname != "127.0.0.1"
            or port is None
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in ("", "/")
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError(
                "CRAWLER_CDP_URL must be an http loopback base URL with an explicit port"
            )
        return value

    @model_validator(mode="after")
    def validate_delays(self) -> "Settings":
        if not self.database_url:
            self.database_url = (
                LOCAL_DATABASE_URL if self.is_local else DOCKER_DATABASE_URL
            )
        if self.is_local and "crawler_browser_mode" not in self.model_fields_set:
            self.crawler_browser_mode = "external_chrome"
        if self.naver_request_delay_max < self.naver_request_delay_min:
            raise ValueError("NAVER_REQUEST_DELAY_MAX must be >= NAVER_REQUEST_DELAY_MIN")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
