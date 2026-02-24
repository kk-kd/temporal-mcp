"""Temporal client wrapper with lazy initialization."""

from typing import Any

from temporalio.client import Client

from temporal_mcp.config import TemporalConfig


class TemporalClientManager:
    """Manages Temporal client connection with lazy initialization."""

    def __init__(self, config: TemporalConfig | None = None) -> None:
        self._config = config or TemporalConfig()
        self._client: Client | None = None

    async def get_client(self) -> Client:
        """Get or create the Temporal client."""
        if self._client is None:
            self._client = await self._create_client()
        return self._client

    async def _create_client(self) -> Client:
        """Create a new Temporal client based on configuration."""
        connect_kwargs: dict[str, Any] = {
            "target_host": self._config.address,
            "namespace": self._config.namespace,
        }

        if self._config.tls_cert and self._config.tls_key:
            from temporalio.client import TLSConfig

            connect_kwargs["tls"] = TLSConfig(
                client_cert=self._config.tls_cert.read_bytes(),
                client_private_key=self._config.tls_key.read_bytes(),
            )
        elif self._config.api_key:
            connect_kwargs["tls"] = True
            connect_kwargs["api_key"] = self._config.api_key

        return await Client.connect(**connect_kwargs)

    async def close(self) -> None:
        """Close the client connection if open."""
        self._client = None
