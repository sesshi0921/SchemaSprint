from enum import StrEnum
from functools import lru_cache
from ipaddress import ip_network
from typing import Literal, Self

from pydantic import AnyHttpUrl, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


class JevMode(StrEnum):
    UNAVAILABLE = "unavailable"
    STUB = "stub"
    EXTERNAL = "external"


class LLMMode(StrEnum):
    """Generation provider selection; assessment remains independently Jev-owned."""

    UNAVAILABLE = "unavailable"
    STUB = "stub"
    GROQ = "groq"


# The edge, Python service, and Rust FFI deliberately share one reversible
# request/payload ceiling.  Smaller per-field limits remain useful for
# validation, but no layer may accept a larger aggregate payload.
MAX_REQUEST_BODY_BYTES = 1024 * 1024


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SCHEMASPRINT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Environment = Environment.DEVELOPMENT
    database_dsn: SecretStr
    session_pepper: SecretStr
    csrf_key: SecretStr
    allowed_origin: AnyHttpUrl
    jev_mode: JevMode = JevMode.UNAVAILABLE
    jev_base_url: AnyHttpUrl | None = None
    jev_api_key: SecretStr | None = None
    llm_mode: LLMMode = LLMMode.UNAVAILABLE
    jev_model: str = "jev-latest"
    jev_timeout_seconds: float = 10.0
    jev_max_retries: int = 2
    # LLM generation is deliberately independent from Jev assessment.  A
    # missing key leaves this provider unavailable; it must never be replaced
    # with a fabricated response.
    groq_api_url: AnyHttpUrl = AnyHttpUrl("https://api.groq.com/openai/v1")
    groq_api_key: SecretStr | None = None
    groq_model: str = "openai/gpt-oss-20b"
    groq_timeout_seconds: float = 20.0
    billing_enabled: Literal[False] = False
    rewarded_ads_enabled: Literal[False] = False
    database_pool_min: int = 1
    database_pool_max: int = 8
    request_body_limit_bytes: int = MAX_REQUEST_BODY_BYTES
    rate_limit_enabled: bool = True
    rate_limit_capacity: int = 120
    rate_limit_window_seconds: int = 60
    rate_limit_max_keys: int = 10_000
    trusted_proxy_cidrs: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_provider_mode(self) -> Self:
        if (
            self.database_pool_min < 1
            or self.database_pool_max < self.database_pool_min
        ):
            raise ValueError("database pool bounds are invalid")
        if not 1 <= self.request_body_limit_bytes <= MAX_REQUEST_BODY_BYTES:
            raise ValueError("request body limit is invalid")
        if self.rate_limit_capacity < 1 or self.rate_limit_capacity > 100_000:
            raise ValueError("rate limit capacity is invalid")
        if not 1 <= self.rate_limit_window_seconds <= 86_400:
            raise ValueError("rate limit window is invalid")
        if not 1 <= self.rate_limit_max_keys <= 1_000_000:
            raise ValueError("rate limit key bound is invalid")
        if not 0 < self.jev_timeout_seconds <= 30:
            raise ValueError("Jev timeout must be between 0 and 30 seconds")
        if not 0 <= self.jev_max_retries <= 3:
            raise ValueError("Jev retries must be between 0 and 3")
        if not 1 <= self.groq_timeout_seconds <= 120:
            raise ValueError("Groq timeout is invalid")
        if not 1 <= len(self.groq_model) <= 128:
            raise ValueError("Groq model is invalid")
        if any(char.isspace() for char in self.groq_model):
            raise ValueError("Groq model cannot contain whitespace")
        for network in self.trusted_proxy_cidrs:
            try:
                ip_network(network, strict=False)
            except ValueError as error:
                raise ValueError("trusted proxy CIDR is invalid") from error
        if self.environment is Environment.PRODUCTION:
            if str(self.allowed_origin).rstrip("/").split(":", 1)[0] != "https":
                raise ValueError("production allowed origin must use HTTPS")
            if not self.rate_limit_enabled:
                raise ValueError("production rate limiting cannot be disabled")
        if len(self.session_pepper.get_secret_value()) < 32:
            raise ValueError("session pepper must contain at least 32 characters")
        if len(self.csrf_key.get_secret_value()) < 32:
            raise ValueError("CSRF key must contain at least 32 characters")
        if self.jev_mode is JevMode.STUB and self.environment not in {
            Environment.DEVELOPMENT,
            Environment.TEST,
        }:
            raise ValueError("Jev stub is restricted to development and test")
        if self.llm_mode is LLMMode.STUB and self.environment not in {
            Environment.DEVELOPMENT,
            Environment.TEST,
        }:
            raise ValueError("LLM stub is restricted to development and test")
        if self.llm_mode is LLMMode.GROQ and (
            self.groq_api_key is None
            or not self.groq_api_key.get_secret_value().strip()
        ):
            raise ValueError("Groq mode requires an API key")
        if self.jev_mode is JevMode.EXTERNAL and (
            self.jev_base_url is None or self.jev_api_key is None
        ):
            raise ValueError("external Jev requires URL and API key")
        if (
            self.jev_mode is JevMode.EXTERNAL
            and self.environment in {Environment.STAGING, Environment.PRODUCTION}
            and self.jev_base_url is not None
            and self.jev_base_url.scheme.lower() != "https"
        ):
            raise ValueError("external Jev URL must use HTTPS outside development")
        if (
            self.groq_api_key is not None
            and self.environment in {Environment.STAGING, Environment.PRODUCTION}
            and self.groq_api_url.scheme.lower() != "https"
        ):
            raise ValueError("Groq URL must use HTTPS outside development")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
