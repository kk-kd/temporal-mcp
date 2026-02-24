"""Tests for configuration module."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from temporal_mcp.config import TemporalConfig


def test_default_config() -> None:
    """Test default configuration values."""
    config = TemporalConfig()

    assert config.address == "localhost:7233"
    assert config.namespace == "default"
    assert config.tls_cert is None
    assert config.tls_key is None
    assert config.api_key is None
    assert config.use_tls is False


def test_config_with_api_key() -> None:
    """Test configuration with API key."""
    config = TemporalConfig(api_key="test-api-key")

    assert config.api_key == "test-api-key"
    assert config.use_tls is True


def test_config_with_tls_certs(tmp_path: Path) -> None:
    """Test configuration with TLS certificates."""
    cert_file = tmp_path / "cert.pem"
    key_file = tmp_path / "key.pem"
    cert_file.write_text("cert content")
    key_file.write_text("key content")

    config = TemporalConfig(
        tls_cert=cert_file,
        tls_key=key_file,
    )

    assert config.tls_cert == cert_file
    assert config.tls_key == key_file
    assert config.use_tls is True


def test_config_tls_requires_both_cert_and_key(tmp_path: Path) -> None:
    """Test that TLS config requires both cert and key."""
    cert_file = tmp_path / "cert.pem"
    cert_file.write_text("cert content")

    with pytest.raises(ValidationError, match="tls_cert and tls_key must be provided"):
        TemporalConfig(tls_cert=cert_file)


def test_config_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test configuration from environment variables."""
    monkeypatch.setenv("TEMPORAL_ADDRESS", "custom.temporal.io:7233")
    monkeypatch.setenv("TEMPORAL_NAMESPACE", "production")

    config = TemporalConfig()

    assert config.address == "custom.temporal.io:7233"
    assert config.namespace == "production"
