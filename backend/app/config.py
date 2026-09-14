from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "merbag IPAM application"
    api_prefix: str = "/api"
    environment: str = "development"
    database_url: str = Field(min_length=1)
    jwt_secret_key: str = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(default=480, ge=5, le=10080)
    max_materialized_addresses: int = Field(default=65536, ge=1, le=1048576)
    cors_origins: str = "http://localhost,http://localhost:3000"
    trusted_hosts: str = "localhost,127.0.0.1,testserver"
    initial_admin_username: str | None = None
    initial_admin_password: str | None = None
    initial_prefix: str | None = "203.0.113.0/24"

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    @property
    def cors_origins_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def trusted_hosts_list(self) -> list[str]:
        return [item.strip() for item in self.trusted_hosts.split(",") if item.strip()]

    @model_validator(mode="after")
    def require_production_secret(self):
        if self.environment.lower() == "production":
            if not self.database_url.startswith("postgresql+psycopg://"):
                raise ValueError("DATABASE_URL must use PostgreSQL with psycopg in production")
            normalized_secret = self.jwt_secret_key.casefold()
            known_placeholder_markers = (
                "change-this",
                "changeme",
                "development-only",
                "replace-me",
            )
            if any(marker in normalized_secret for marker in known_placeholder_markers):
                raise ValueError("JWT_SECRET_KEY must not be a known placeholder in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
