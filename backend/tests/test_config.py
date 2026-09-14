import pytest
from pydantic import ValidationError

from app.config import Settings


def test_comma_separated_proxy_settings_are_normalized():
    config = Settings(
        database_url="sqlite+pysqlite:///:memory:",
        jwt_secret_key="01234567890123456789012345678901",
        cors_origins="https://one.example, https://two.example",
        trusted_hosts="one.example,two.example",
        environment="test",
    )
    assert config.cors_origins_list == ["https://one.example", "https://two.example"]
    assert config.trusted_hosts_list == ["one.example", "two.example"]


def test_production_rejects_development_jwt_secret():
    with pytest.raises(ValidationError):
        Settings(
            database_url="postgresql+psycopg://merbag@db/merbag",
            jwt_secret_key="development-only-change-this-secret",
            environment="production",
        )
