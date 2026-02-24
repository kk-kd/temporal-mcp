"""MCP server for Temporal workflow debugging."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from fastmcp import FastMCP

logger = logging.getLogger(__name__)
from temporalio.client import WorkflowExecutionStatus

from temporal_mcp.client import TemporalClientManager
from temporal_mcp.config import TemporalConfig
from temporal_mcp.models import (
    HistoryEvent,
    PendingActivity,
    WorkflowDescription,
    WorkflowHistory,
    WorkflowStatus,
    WorkflowSummary,
)

if TYPE_CHECKING:
    from temporalio.client import Client

mcp = FastMCP("temporal")
_client_manager: TemporalClientManager | None = None


def _get_client_manager() -> TemporalClientManager:
    """Get or create the client manager singleton."""
    global _client_manager
    if _client_manager is None:
        _client_manager = TemporalClientManager(TemporalConfig())
    return _client_manager


def _map_status(status: WorkflowExecutionStatus | None) -> WorkflowStatus:
    """Map Temporal status enum to our model."""
    if status is None:
        return WorkflowStatus.UNKNOWN
    mapping: dict[WorkflowExecutionStatus, WorkflowStatus] = {
        WorkflowExecutionStatus.RUNNING: WorkflowStatus.RUNNING,
        WorkflowExecutionStatus.COMPLETED: WorkflowStatus.COMPLETED,
        WorkflowExecutionStatus.FAILED: WorkflowStatus.FAILED,
        WorkflowExecutionStatus.CANCELED: WorkflowStatus.CANCELED,
        WorkflowExecutionStatus.TERMINATED: WorkflowStatus.TERMINATED,
        WorkflowExecutionStatus.CONTINUED_AS_NEW: WorkflowStatus.CONTINUED_AS_NEW,
        WorkflowExecutionStatus.TIMED_OUT: WorkflowStatus.TIMED_OUT,
    }
    return mapping.get(status, WorkflowStatus.UNKNOWN)


def _format_event_details(event: Any) -> str:
    """Format event attributes into a human-readable string."""
    event_type = getattr(event, "event_type", None)
    if event_type is None:
        return "No details available"

    type_name: str = event_type.name if hasattr(event_type, "name") else str(event_type)

    details_parts: list[str] = []

    if type_name == "EVENT_TYPE_WORKFLOW_EXECUTION_STARTED":
        attrs = getattr(event, "workflow_execution_started_event_attributes", None)
        if attrs:
            wf_type = getattr(attrs, "workflow_type", None)
            if wf_type:
                details_parts.append(f"type={getattr(wf_type, 'name', 'unknown')}")
            task_queue = getattr(attrs, "task_queue", None)
            if task_queue:
                details_parts.append(f"queue={getattr(task_queue, 'name', 'unknown')}")

    elif type_name == "EVENT_TYPE_WORKFLOW_EXECUTION_COMPLETED":
        details_parts.append("Workflow completed successfully")

    elif type_name == "EVENT_TYPE_WORKFLOW_EXECUTION_FAILED":
        attrs = getattr(event, "workflow_execution_failed_event_attributes", None)
        if attrs:
            failure = getattr(attrs, "failure", None)
            if failure:
                msg = getattr(failure, "message", "Unknown error")
                details_parts.append(f"error={msg}")

    elif type_name == "EVENT_TYPE_ACTIVITY_TASK_SCHEDULED":
        attrs = getattr(event, "activity_task_scheduled_event_attributes", None)
        if attrs:
            activity_type = getattr(attrs, "activity_type", None)
            if activity_type:
                details_parts.append(
                    f"activity={getattr(activity_type, 'name', 'unknown')}"
                )

    elif type_name == "EVENT_TYPE_ACTIVITY_TASK_STARTED":
        details_parts.append("Activity started")

    elif type_name == "EVENT_TYPE_ACTIVITY_TASK_COMPLETED":
        details_parts.append("Activity completed")

    elif type_name == "EVENT_TYPE_ACTIVITY_TASK_FAILED":
        attrs = getattr(event, "activity_task_failed_event_attributes", None)
        if attrs:
            failure = getattr(attrs, "failure", None)
            if failure:
                msg = getattr(failure, "message", "Unknown error")
                details_parts.append(f"error={msg}")

    elif type_name == "EVENT_TYPE_TIMER_STARTED":
        attrs = getattr(event, "timer_started_event_attributes", None)
        if attrs:
            timer_id = getattr(attrs, "timer_id", None)
            if timer_id:
                details_parts.append(f"timer_id={timer_id}")

    elif type_name == "EVENT_TYPE_TIMER_FIRED":
        attrs = getattr(event, "timer_fired_event_attributes", None)
        if attrs:
            timer_id = getattr(attrs, "timer_id", None)
            if timer_id:
                details_parts.append(f"timer_id={timer_id}")

    if not details_parts:
        clean_type = type_name.replace("EVENT_TYPE_", "").replace("_", " ").title()
        return clean_type

    return ", ".join(details_parts)


@mcp.tool()
async def list_workflows(query: str = "", limit: int = 10) -> str:
    """List workflow executions from Temporal.

    Args:
        query: Optional query filter (Temporal list filter syntax).
               Example: 'WorkflowType="MyWorkflow" AND ExecutionStatus="Running"'
        limit: Maximum number of workflows to return (default 10, max 100)
    """
    limit = min(max(1, limit), 100)

    client: Client = await _get_client_manager().get_client()
    workflows: list[WorkflowSummary] = []

    async for wf in client.list_workflows(query=query if query else None):
        if len(workflows) >= limit:
            break

        workflows.append(
            WorkflowSummary(
                workflow_id=wf.id,
                run_id=wf.run_id or "",
                workflow_type=wf.workflow_type or "unknown",
                status=_map_status(wf.status),
                start_time=wf.start_time,
                close_time=wf.close_time,
                task_queue=wf.task_queue or "unknown",
            )
        )

    if not workflows:
        return "No workflows found matching the query."

    lines = [f"Found {len(workflows)} workflow(s):\n"]
    for workflow in workflows:
        start = (
            workflow.start_time.strftime("%Y-%m-%d %H:%M:%S")
            if workflow.start_time
            else "N/A"
        )
        status_str = str(workflow.status.value) if workflow.status else "UNKNOWN"
        lines.append(
            f"- {workflow.workflow_id} ({workflow.workflow_type})\n"
            f"  Status: {status_str} | Started: {start} | Queue: {workflow.task_queue}"
        )

    return "\n".join(lines)


@mcp.tool()
async def describe_workflow(workflow_id: str, run_id: str = "") -> str:
    """Get detailed information about a specific workflow execution.

    Args:
        workflow_id: The workflow ID to describe
        run_id: Optional run ID (uses latest run if not specified)
    """
    client: Client = await _get_client_manager().get_client()
    handle = client.get_workflow_handle(workflow_id, run_id=run_id if run_id else None)

    try:
        desc = await handle.describe()
    except Exception as e:
        return f"Error describing workflow: {e}"

    pending_activities: list[PendingActivity] = []
    for pa in desc.raw_description.pending_activities:
        last_failure: str | None = None
        if pa.last_failure and pa.last_failure.message:
            last_failure = pa.last_failure.message

        activity_type_name = "unknown"
        if pa.activity_type:
            activity_type_name = getattr(pa.activity_type, "name", "unknown")
        state_name = "unknown"
        if pa.state:
            state_name = getattr(pa.state, "name", "unknown")

        pending_activities.append(
            PendingActivity(
                activity_id=pa.activity_id,
                activity_type=activity_type_name,
                state=state_name,
                attempt=pa.attempt,
                last_failure=last_failure,
            )
        )

    memo: dict[str, str] = {}
    try:
        memo_data = await desc.memo()
        if memo_data:
            for key in memo_data:
                memo[key] = str(memo_data.get(key, ""))
    except Exception:
        pass

    search_attrs: dict[str, str] = {}
    try:
        sa_data = await desc.search_attributes()  # type: ignore[operator]
        if sa_data:
            for key in sa_data:
                search_attrs[key] = str(sa_data.get(key, ""))
    except Exception:
        pass

    workflow_desc = WorkflowDescription(
        workflow_id=desc.id,
        run_id=desc.run_id or "",
        workflow_type=desc.workflow_type or "unknown",
        status=_map_status(desc.status),
        start_time=desc.start_time,
        close_time=desc.close_time,
        execution_time=desc.execution_time,
        task_queue=desc.task_queue or "unknown",
        history_length=desc.history_length,
        pending_activities=pending_activities,
        memo=memo,
        search_attributes=search_attrs,
    )

    lines = [
        f"Workflow: {workflow_desc.workflow_id}",
        f"Run ID: {workflow_desc.run_id}",
        f"Type: {workflow_desc.workflow_type}",
        f"Status: {workflow_desc.status.value}",
        f"Task Queue: {workflow_desc.task_queue}",
        f"History Length: {workflow_desc.history_length} events",
    ]

    if workflow_desc.start_time:
        lines.append(
            f"Started: {workflow_desc.start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}"
        )
    if workflow_desc.close_time:
        lines.append(
            f"Closed: {workflow_desc.close_time.strftime('%Y-%m-%d %H:%M:%S UTC')}"
        )

    if workflow_desc.pending_activities:
        lines.append(f"\nPending Activities ({len(workflow_desc.pending_activities)}):")
        for pending in workflow_desc.pending_activities:
            lines.append(
                f"  - {pending.activity_type} (id={pending.activity_id}, "
                f"attempt={pending.attempt}, state={pending.state})"
            )
            if pending.last_failure:
                lines.append(f"    Last failure: {pending.last_failure}")

    if workflow_desc.memo:
        lines.append("\nMemo:")
        for key, value in workflow_desc.memo.items():
            lines.append(f"  {key}: {value}")

    if workflow_desc.search_attributes:
        lines.append("\nSearch Attributes:")
        for key, value in workflow_desc.search_attributes.items():
            lines.append(f"  {key}: {value}")

    return "\n".join(lines)


@mcp.tool()
async def get_workflow_history(
    workflow_id: str, run_id: str = "", max_events: int = 100
) -> str:
    """Get the event history for a workflow execution.

    Args:
        workflow_id: The workflow ID
        run_id: Optional run ID (uses latest run if not specified)
        max_events: Maximum number of events to return (default 100, max 1000)
    """
    max_events = min(max(1, max_events), 1000)

    client: Client = await _get_client_manager().get_client()
    handle = client.get_workflow_handle(workflow_id, run_id=run_id if run_id else None)

    events: list[HistoryEvent] = []
    total_events = 0
    truncated = False

    try:
        async for event in handle.fetch_history_events():
            total_events += 1
            if len(events) >= max_events:
                truncated = True
                continue

            event_time: datetime | None = None
            raw_time = getattr(event, "event_time", None)
            if raw_time is not None:
                if hasattr(raw_time, "ToDatetime"):
                    event_time = raw_time.ToDatetime(tzinfo=UTC)
                elif isinstance(raw_time, datetime):
                    event_time = raw_time

            event_type_name = "UNKNOWN"
            if hasattr(event, "event_type"):
                et = event.event_type
                event_type_name = et.name if hasattr(et, "name") else str(et)

            events.append(
                HistoryEvent(
                    event_id=event.event_id,
                    event_time=event_time,
                    event_type=event_type_name.replace("EVENT_TYPE_", ""),
                    details=_format_event_details(event),
                )
            )
    except Exception as e:
        return f"Error fetching workflow history: {e}"

    history = WorkflowHistory(
        workflow_id=workflow_id,
        run_id=run_id or "latest",
        events=events,
        total_events=total_events,
        truncated=truncated,
    )

    lines = [
        f"Workflow History: {history.workflow_id}",
        f"Run ID: {history.run_id}",
        f"Events: {len(history.events)}"
        + (f" of {history.total_events}" if history.truncated else ""),
        "",
    ]

    for evt in history.events:
        time_str = (
            evt.event_time.strftime("%H:%M:%S.%f")[:-3] if evt.event_time else "N/A"
        )
        lines.append(f"[{evt.event_id:4d}] {time_str} | {evt.event_type}")
        if evt.details and evt.details != evt.event_type.replace("_", " ").title():
            lines.append(f"       {evt.details}")

    if history.truncated:
        lines.append(
            f"\n... truncated (showing {len(history.events)} "
            f"of {history.total_events} events)"
        )

    return "\n".join(lines)


def main() -> None:
    """Run the MCP server."""
    logging.basicConfig(level=logging.INFO)
    logger.info("Starting Temporal MCP server...")
    mcp.run()


if __name__ == "__main__":
    main()
