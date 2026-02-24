"""Configuration for Temporal MCP server."""

from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class TemporalConfig(BaseSettings):
    """Configuration for connecting to Temporal server."""

    model_config = SettingsConfigDict(env_prefix="TEMPORAL_")

    address: str = Field(
        default="localhost:7233",
        description="Temporal server address",
    )
    namespace: str = Field(
        default="default",
        description="Temporal namespace",
    )
    tls_cert: Path | None = Field(
        default=None,
        description="Path to TLS certificate file (for Temporal Cloud)",
    )
    tls_key: Path | None = Field(
        default=None,
        description="Path to TLS key file (for Temporal Cloud)",
    )
    api_key: str | None = Field(
        default=None,
        description="API key for Temporal Cloud (alternative to TLS cert)",
    )

    @model_validator(mode="after")
    def validate_tls_config(self) -> "TemporalConfig":
        """Validate that TLS cert and key are provided together."""
        if (self.tls_cert is None) != (self.tls_key is None):
            raise ValueError("Both tls_cert and tls_key must be provided together")
        return self

    @property
    def use_tls(self) -> bool:
        """Check if TLS should be used for connection."""
        return self.tls_cert is not None or self.api_key is not None
