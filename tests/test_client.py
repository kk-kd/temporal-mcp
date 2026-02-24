"""Tests for Temporal client wrapper."""

import pytest

from temporal_mcp.client import TemporalClientManager
from temporal_mcp.config import TemporalConfig


def test_client_manager_initialization() -> None:
    """Test client manager initializes with config."""
    config = TemporalConfig(
        address="test.temporal.io:7233",
        namespace="test-ns",
    )
    manager = TemporalClientManager(config)

    assert manager._config == config
    assert manager._client is None


def test_client_manager_default_config() -> None:
    """Test client manager uses default config if none provided."""
    manager = TemporalClientManager()

    assert manager._config.address == "localhost:7233"
    assert manager._config.namespace == "default"


@pytest.mark.asyncio
async def test_client_manager_close() -> None:
    """Test client manager close clears client."""
    manager = TemporalClientManager()
    manager._client = object()  # type: ignore[assignment]

    await manager.close()

    assert manager._client is None
