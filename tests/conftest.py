"""Pytest configuration and fixtures."""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from temporal_mcp.client import TemporalClientManager
from temporal_mcp.config import TemporalConfig


@pytest.fixture
def temporal_config() -> TemporalConfig:
    """Create a test Temporal configuration."""
    return TemporalConfig(
        address="localhost:7233",
        namespace="test-namespace",
    )


@pytest.fixture
def mock_workflow_execution() -> MagicMock:
    """Create a mock workflow execution for listing."""
    wf = MagicMock()
    wf.id = "test-workflow-id"
    wf.run_id = "test-run-id"
    wf.workflow_type = "TestWorkflow"
    wf.status = MagicMock()
    wf.status.name = "WORKFLOW_EXECUTION_STATUS_RUNNING"
    wf.start_time = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)
    wf.close_time = None
    wf.task_queue = "test-queue"
    return wf


@pytest.fixture
def mock_workflow_description() -> MagicMock:
    """Create a mock workflow description."""
    desc = MagicMock()
    desc.id = "test-workflow-id"
    desc.run_id = "test-run-id"
    desc.workflow_type = "TestWorkflow"
    desc.status = MagicMock()
    desc.status.name = "WORKFLOW_EXECUTION_STATUS_COMPLETED"
    desc.start_time = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)
    desc.close_time = datetime(2024, 1, 15, 10, 35, 0, tzinfo=UTC)
    desc.execution_time = datetime(2024, 1, 15, 10, 30, 1, tzinfo=UTC)
    desc.task_queue = "test-queue"
    desc.history_length = 25
    desc.raw_description = MagicMock()
    desc.raw_description.pending_activities = []

    async def mock_memo() -> dict[str, Any]:
        return {"key1": "value1"}

    async def mock_search_attrs() -> dict[str, Any]:
        return {"CustomField": "custom-value"}

    desc.memo = mock_memo
    desc.search_attributes = mock_search_attrs

    return desc


@pytest.fixture
def mock_history_event() -> MagicMock:
    """Create a mock history event."""
    event = MagicMock()
    event.event_id = 1
    event.event_time = MagicMock()
    event.event_time.ToDatetime.return_value = datetime(
        2024, 1, 15, 10, 30, 0, tzinfo=UTC
    )
    event.event_type = MagicMock()
    event.event_type.name = "EVENT_TYPE_WORKFLOW_EXECUTION_STARTED"
    event.workflow_execution_started_event_attributes = MagicMock()
    event.workflow_execution_started_event_attributes.workflow_type = MagicMock()
    event.workflow_execution_started_event_attributes.workflow_type.name = (
        "TestWorkflow"
    )
    event.workflow_execution_started_event_attributes.task_queue = MagicMock()
    event.workflow_execution_started_event_attributes.task_queue.name = "test-queue"
    return event


@pytest.fixture
def mock_temporal_client(
    mock_workflow_execution: MagicMock,
    mock_workflow_description: MagicMock,
    mock_history_event: MagicMock,
) -> MagicMock:
    """Create a mock Temporal client."""
    client = MagicMock()

    async def mock_list_workflows(
        query: str | None = None,  # noqa: ARG001
    ) -> AsyncGenerator[MagicMock, None]:
        yield mock_workflow_execution

    client.list_workflows = mock_list_workflows

    handle = MagicMock()
    handle.describe = AsyncMock(return_value=mock_workflow_description)

    async def mock_fetch_history() -> AsyncGenerator[MagicMock, None]:
        yield mock_history_event

    handle.fetch_history_events = mock_fetch_history
    client.get_workflow_handle = MagicMock(return_value=handle)

    return client


@pytest.fixture
def mock_client_manager(mock_temporal_client: MagicMock) -> TemporalClientManager:
    """Create a mock client manager."""
    manager = TemporalClientManager(TemporalConfig())
    manager._client = mock_temporal_client
    return manager
