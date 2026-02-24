"""Tests for MCP server and tools."""

from unittest.mock import MagicMock, patch

import pytest

from temporal_mcp import server
from temporal_mcp.models import WorkflowStatus


def test_map_status_running() -> None:
    """Test status mapping for running workflows."""
    from temporalio.client import WorkflowExecutionStatus

    result = server._map_status(WorkflowExecutionStatus.RUNNING)
    assert result == WorkflowStatus.RUNNING


def test_map_status_completed() -> None:
    """Test status mapping for completed workflows."""
    from temporalio.client import WorkflowExecutionStatus

    result = server._map_status(WorkflowExecutionStatus.COMPLETED)
    assert result == WorkflowStatus.COMPLETED


def test_map_status_none() -> None:
    """Test status mapping for None."""
    result = server._map_status(None)
    assert result == WorkflowStatus.UNKNOWN


def test_format_event_details_workflow_started() -> None:
    """Test event formatting for workflow started."""
    event = MagicMock()
    event.event_type = MagicMock()
    event.event_type.name = "EVENT_TYPE_WORKFLOW_EXECUTION_STARTED"
    event.workflow_execution_started_event_attributes = MagicMock()
    event.workflow_execution_started_event_attributes.workflow_type = MagicMock()
    event.workflow_execution_started_event_attributes.workflow_type.name = "TestWF"
    event.workflow_execution_started_event_attributes.task_queue = MagicMock()
    event.workflow_execution_started_event_attributes.task_queue.name = "test-queue"

    result = server._format_event_details(event)

    assert "type=TestWF" in result
    assert "queue=test-queue" in result


def test_format_event_details_workflow_completed() -> None:
    """Test event formatting for workflow completed."""
    event = MagicMock()
    event.event_type = MagicMock()
    event.event_type.name = "EVENT_TYPE_WORKFLOW_EXECUTION_COMPLETED"

    result = server._format_event_details(event)

    assert "completed successfully" in result


def test_format_event_details_activity_scheduled() -> None:
    """Test event formatting for activity scheduled."""
    event = MagicMock()
    event.event_type = MagicMock()
    event.event_type.name = "EVENT_TYPE_ACTIVITY_TASK_SCHEDULED"
    event.activity_task_scheduled_event_attributes = MagicMock()
    event.activity_task_scheduled_event_attributes.activity_type = MagicMock()
    event.activity_task_scheduled_event_attributes.activity_type.name = "TestActivity"

    result = server._format_event_details(event)

    assert "activity=TestActivity" in result


def test_format_event_details_no_type() -> None:
    """Test event formatting when event type is missing."""
    event = MagicMock(spec=[])

    result = server._format_event_details(event)

    assert result == "No details available"


@pytest.mark.asyncio
async def test_list_workflows_empty(
    mock_client_manager: MagicMock,
) -> None:
    """Test listing workflows when none exist."""
    from collections.abc import AsyncGenerator

    async def empty_generator(
        query: str | None = None,  # noqa: ARG001
    ) -> AsyncGenerator[MagicMock, None]:
        return
        yield  # type: ignore[misc]

    mock_client_manager._client.list_workflows = empty_generator

    with patch.object(server, "_get_client_manager", return_value=mock_client_manager):
        result = await server.list_workflows()

    assert "No workflows found" in result


@pytest.mark.asyncio
async def test_list_workflows_with_results(
    mock_client_manager: MagicMock,
    mock_workflow_execution: MagicMock,
) -> None:
    """Test listing workflows with results."""
    from temporalio.client import WorkflowExecutionStatus

    mock_workflow_execution.status = WorkflowExecutionStatus.RUNNING

    with patch.object(server, "_get_client_manager", return_value=mock_client_manager):
        result = await server.list_workflows()

    assert "test-workflow-id" in result
    assert "TestWorkflow" in result


@pytest.mark.asyncio
async def test_describe_workflow(
    mock_client_manager: MagicMock,
) -> None:
    """Test describing a workflow."""
    from temporalio.client import WorkflowExecutionStatus

    mock_client_manager._client.get_workflow_handle().describe.return_value.status = (
        WorkflowExecutionStatus.COMPLETED
    )

    with patch.object(server, "_get_client_manager", return_value=mock_client_manager):
        result = await server.describe_workflow("test-workflow-id")

    assert "test-workflow-id" in result
    assert "test-run-id" in result


@pytest.mark.asyncio
async def test_describe_workflow_error(
    mock_client_manager: MagicMock,
) -> None:
    """Test describing a workflow that errors."""
    mock_client_manager._client.get_workflow_handle().describe.side_effect = Exception(
        "Workflow not found"
    )

    with patch.object(server, "_get_client_manager", return_value=mock_client_manager):
        result = await server.describe_workflow("nonexistent-id")

    assert "Error" in result
    assert "Workflow not found" in result


@pytest.mark.asyncio
async def test_get_workflow_history(
    mock_client_manager: MagicMock,
) -> None:
    """Test getting workflow history."""
    with patch.object(server, "_get_client_manager", return_value=mock_client_manager):
        result = await server.get_workflow_history("test-workflow-id")

    assert "Workflow History" in result
    assert "test-workflow-id" in result
    assert "WORKFLOW_EXECUTION_STARTED" in result


@pytest.mark.asyncio
async def test_get_workflow_history_with_limit(
    mock_client_manager: MagicMock,
) -> None:
    """Test getting workflow history respects limit."""
    with patch.object(server, "_get_client_manager", return_value=mock_client_manager):
        result = await server.get_workflow_history("test-workflow-id", max_events=5)

    assert "Workflow History" in result


@pytest.mark.asyncio
async def test_get_workflow_history_error(
    mock_client_manager: MagicMock,
) -> None:
    """Test getting workflow history that errors."""

    async def error_generator() -> None:
        raise Exception("History fetch failed")
        yield  # type: ignore[misc]

    mock_client_manager._client.get_workflow_handle().fetch_history_events = (
        error_generator
    )

    with patch.object(server, "_get_client_manager", return_value=mock_client_manager):
        result = await server.get_workflow_history("test-workflow-id")

    assert "Error" in result
    assert "History fetch failed" in result
