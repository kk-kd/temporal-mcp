"""MCP server for Temporal workflow debugging."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from fastmcp import FastMCP

logger = logging.getLogger(__name__)
from temporalio.client import WorkflowExecutionStatus

from temporal_mcp.client import TemporalClientManager
from temporal_mcp.config import TemporalConfig
from temporal_mcp.models import (
    ActivityTiming,
    EventPayload,
    HistoryEvent,
    PendingActivity,
    WorkflowDescription,
    WorkflowError,
    WorkflowHistory,
    WorkflowStatus,
    WorkflowSummary,
    WorkflowTimeline,
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


def _extract_payload_data(payloads: Any) -> str:
    """Extract and decode payload data to JSON string."""
    if payloads is None:
        return "null"

    try:
        payload_list = list(payloads) if hasattr(payloads, "__iter__") else [payloads]
        if not payload_list:
            return "null"

        decoded_values: list[Any] = []
        for payload in payload_list:
            data = getattr(payload, "data", None)
            if data is None:
                decoded_values.append(None)
                continue

            try:
                decoded = data.decode("utf-8") if isinstance(data, bytes) else str(data)
                try:
                    decoded_values.append(json.loads(decoded))
                except json.JSONDecodeError:
                    decoded_values.append(decoded)
            except Exception:
                decoded_values.append(f"<binary data: {len(data)} bytes>")

        if len(decoded_values) == 1:
            return json.dumps(decoded_values[0], indent=2, default=str)
        return json.dumps(decoded_values, indent=2, default=str)
    except Exception as e:
        return f"<error decoding payload: {e}>"


def _extract_failure_details(failure: Any) -> tuple[str, str | None, str | None, str | None]:
    """Extract error details from a failure object.

    Returns (message, error_type, stack_trace, cause_chain).
    """
    if failure is None:
        return ("Unknown error", None, None, None)

    message = getattr(failure, "message", "Unknown error") or "Unknown error"
    error_type = None
    stack_trace = None
    cause_chain: list[str] = []

    if hasattr(failure, "application_failure_info"):
        app_info = failure.application_failure_info
        if app_info:
            error_type = getattr(app_info, "type", None)

    if hasattr(failure, "stack_trace"):
        stack_trace = failure.stack_trace

    current = getattr(failure, "cause", None)
    while current is not None:
        cause_msg = getattr(current, "message", None)
        if cause_msg:
            cause_chain.append(cause_msg)
        current = getattr(current, "cause", None)

    cause_str = " -> ".join(cause_chain) if cause_chain else None
    return (message, error_type, stack_trace, cause_str)


@mcp.tool()
async def get_event_payloads(
    workflow_id: str,
    run_id: str = "",
    event_types: str = "",
) -> str:
    """Extract input/output payloads from workflow events for debugging.

    This tool retrieves the actual data passed to and returned from activities,
    signals, queries, and the workflow itself.

    Args:
        workflow_id: The workflow ID
        run_id: Optional run ID (uses latest run if not specified)
        event_types: Comma-separated list of event types to filter.
                     Options: workflow_input, workflow_output, activity_input,
                     activity_output, signal, child_workflow_input, child_workflow_output.
                     Leave empty for all payload events.
    """
    client: Client = await _get_client_manager().get_client()
    handle = client.get_workflow_handle(workflow_id, run_id=run_id if run_id else None)

    filter_types: set[str] = set()
    if event_types:
        filter_types = {t.strip().lower() for t in event_types.split(",")}

    payloads: list[EventPayload] = []
    scheduled_activities: dict[int, tuple[str, str]] = {}

    try:
        async for event in handle.fetch_history_events():
            event_time: datetime | None = None
            raw_time = getattr(event, "event_time", None)
            if raw_time is not None:
                if hasattr(raw_time, "ToDatetime"):
                    event_time = raw_time.ToDatetime(tzinfo=UTC)
                elif isinstance(raw_time, datetime):
                    event_time = raw_time

            event_type_enum = getattr(event, "event_type", None)
            if event_type_enum is None:
                continue
            type_name = (
                event_type_enum.name if hasattr(event_type_enum, "name") else str(event_type_enum)
            )

            if type_name == "EVENT_TYPE_WORKFLOW_EXECUTION_STARTED":
                if filter_types and "workflow_input" not in filter_types:
                    continue
                attrs = getattr(event, "workflow_execution_started_event_attributes", None)
                if attrs:
                    input_data = getattr(attrs, "input", None)
                    payloads.append(
                        EventPayload(
                            event_id=event.event_id,
                            event_type="WORKFLOW_EXECUTION_STARTED",
                            event_time=event_time,
                            payload_type="workflow_input",
                            data=_extract_payload_data(input_data),
                        )
                    )

            elif type_name == "EVENT_TYPE_WORKFLOW_EXECUTION_COMPLETED":
                if filter_types and "workflow_output" not in filter_types:
                    continue
                attrs = getattr(event, "workflow_execution_completed_event_attributes", None)
                if attrs:
                    result_data = getattr(attrs, "result", None)
                    payloads.append(
                        EventPayload(
                            event_id=event.event_id,
                            event_type="WORKFLOW_EXECUTION_COMPLETED",
                            event_time=event_time,
                            payload_type="workflow_output",
                            data=_extract_payload_data(result_data),
                        )
                    )

            elif type_name == "EVENT_TYPE_ACTIVITY_TASK_SCHEDULED":
                attrs = getattr(event, "activity_task_scheduled_event_attributes", None)
                if attrs:
                    activity_type = getattr(attrs, "activity_type", None)
                    activity_name = getattr(activity_type, "name", "unknown") if activity_type else "unknown"
                    activity_id = getattr(attrs, "activity_id", "unknown")
                    scheduled_activities[event.event_id] = (activity_name, activity_id)

                    if not filter_types or "activity_input" in filter_types:
                        input_data = getattr(attrs, "input", None)
                        payloads.append(
                            EventPayload(
                                event_id=event.event_id,
                                event_type=f"ACTIVITY_TASK_SCHEDULED ({activity_name})",
                                event_time=event_time,
                                payload_type="activity_input",
                                data=_extract_payload_data(input_data),
                            )
                        )

            elif type_name == "EVENT_TYPE_ACTIVITY_TASK_COMPLETED":
                if filter_types and "activity_output" not in filter_types:
                    continue
                attrs = getattr(event, "activity_task_completed_event_attributes", None)
                if attrs:
                    scheduled_id = getattr(attrs, "scheduled_event_id", None)
                    activity_info = scheduled_activities.get(scheduled_id, ("unknown", "unknown"))
                    result_data = getattr(attrs, "result", None)
                    payloads.append(
                        EventPayload(
                            event_id=event.event_id,
                            event_type=f"ACTIVITY_TASK_COMPLETED ({activity_info[0]})",
                            event_time=event_time,
                            payload_type="activity_output",
                            data=_extract_payload_data(result_data),
                            related_event_id=scheduled_id,
                        )
                    )

            elif type_name == "EVENT_TYPE_WORKFLOW_EXECUTION_SIGNALED":
                if filter_types and "signal" not in filter_types:
                    continue
                attrs = getattr(event, "workflow_execution_signaled_event_attributes", None)
                if attrs:
                    signal_name = getattr(attrs, "signal_name", "unknown")
                    input_data = getattr(attrs, "input", None)
                    payloads.append(
                        EventPayload(
                            event_id=event.event_id,
                            event_type=f"WORKFLOW_EXECUTION_SIGNALED ({signal_name})",
                            event_time=event_time,
                            payload_type="signal",
                            data=_extract_payload_data(input_data),
                        )
                    )

            elif type_name == "EVENT_TYPE_START_CHILD_WORKFLOW_EXECUTION_INITIATED":
                if filter_types and "child_workflow_input" not in filter_types:
                    continue
                attrs = getattr(
                    event, "start_child_workflow_execution_initiated_event_attributes", None
                )
                if attrs:
                    wf_type = getattr(attrs, "workflow_type", None)
                    wf_name = getattr(wf_type, "name", "unknown") if wf_type else "unknown"
                    input_data = getattr(attrs, "input", None)
                    payloads.append(
                        EventPayload(
                            event_id=event.event_id,
                            event_type=f"CHILD_WORKFLOW_INITIATED ({wf_name})",
                            event_time=event_time,
                            payload_type="child_workflow_input",
                            data=_extract_payload_data(input_data),
                        )
                    )

            elif type_name == "EVENT_TYPE_CHILD_WORKFLOW_EXECUTION_COMPLETED":
                if filter_types and "child_workflow_output" not in filter_types:
                    continue
                attrs = getattr(
                    event, "child_workflow_execution_completed_event_attributes", None
                )
                if attrs:
                    result_data = getattr(attrs, "result", None)
                    payloads.append(
                        EventPayload(
                            event_id=event.event_id,
                            event_type="CHILD_WORKFLOW_COMPLETED",
                            event_time=event_time,
                            payload_type="child_workflow_output",
                            data=_extract_payload_data(result_data),
                        )
                    )

    except Exception as e:
        return f"Error fetching workflow events: {e}"

    if not payloads:
        return f"No payload events found for workflow {workflow_id}."

    lines = [
        f"Event Payloads for Workflow: {workflow_id}",
        f"Run ID: {run_id or 'latest'}",
        f"Found {len(payloads)} payload event(s)",
        "",
    ]

    for p in payloads:
        time_str = p.event_time.strftime("%H:%M:%S.%f")[:-3] if p.event_time else "N/A"
        lines.append(f"[{p.event_id:4d}] {time_str} | {p.event_type}")
        lines.append(f"       Type: {p.payload_type}")
        if p.related_event_id:
            lines.append(f"       Related Event: {p.related_event_id}")
        lines.append(f"       Data: {p.data}")
        lines.append("")

    return "\n".join(lines)


@mcp.tool()
async def get_workflow_errors(
    workflow_id: str,
    run_id: str = "",
    include_retries: bool = True,
) -> str:
    """Get all errors and failures from a workflow execution.

    Aggregates all failure events with full error messages, stack traces,
    and retry information for debugging.

    Args:
        workflow_id: The workflow ID
        run_id: Optional run ID (uses latest run if not specified)
        include_retries: Include intermediate retry failures (default True)
    """
    client: Client = await _get_client_manager().get_client()
    handle = client.get_workflow_handle(workflow_id, run_id=run_id if run_id else None)

    errors: list[WorkflowError] = []
    scheduled_activities: dict[int, tuple[str, str]] = {}
    activity_attempts: dict[str, int] = {}

    try:
        async for event in handle.fetch_history_events():
            event_time: datetime | None = None
            raw_time = getattr(event, "event_time", None)
            if raw_time is not None:
                if hasattr(raw_time, "ToDatetime"):
                    event_time = raw_time.ToDatetime(tzinfo=UTC)
                elif isinstance(raw_time, datetime):
                    event_time = raw_time

            event_type_enum = getattr(event, "event_type", None)
            if event_type_enum is None:
                continue
            type_name = (
                event_type_enum.name if hasattr(event_type_enum, "name") else str(event_type_enum)
            )

            if type_name == "EVENT_TYPE_ACTIVITY_TASK_SCHEDULED":
                attrs = getattr(event, "activity_task_scheduled_event_attributes", None)
                if attrs:
                    activity_type = getattr(attrs, "activity_type", None)
                    activity_name = getattr(activity_type, "name", "unknown") if activity_type else "unknown"
                    activity_id = getattr(attrs, "activity_id", "unknown")
                    scheduled_activities[event.event_id] = (activity_name, activity_id)

            elif type_name == "EVENT_TYPE_ACTIVITY_TASK_FAILED":
                attrs = getattr(event, "activity_task_failed_event_attributes", None)
                if attrs:
                    scheduled_id = getattr(attrs, "scheduled_event_id", None)
                    activity_info = scheduled_activities.get(scheduled_id, ("unknown", "unknown"))
                    activity_id = activity_info[1]

                    activity_attempts[activity_id] = activity_attempts.get(activity_id, 0) + 1
                    attempt = activity_attempts[activity_id]

                    failure = getattr(attrs, "failure", None)
                    msg, err_type, stack, cause = _extract_failure_details(failure)

                    retry_state = getattr(attrs, "retry_state", None)
                    is_final = retry_state is not None and "NON_RETRYABLE" in str(retry_state)

                    if include_retries or is_final or attempt == 1:
                        errors.append(
                            WorkflowError(
                                event_id=event.event_id,
                                event_type="ACTIVITY_TASK_FAILED",
                                event_time=event_time,
                                error_message=msg,
                                error_type=err_type,
                                stack_trace=stack,
                                activity_type=activity_info[0],
                                activity_id=activity_id,
                                attempt=attempt,
                                cause=cause,
                            )
                        )

            elif type_name == "EVENT_TYPE_ACTIVITY_TASK_TIMED_OUT":
                attrs = getattr(event, "activity_task_timed_out_event_attributes", None)
                if attrs:
                    scheduled_id = getattr(attrs, "scheduled_event_id", None)
                    activity_info = scheduled_activities.get(scheduled_id, ("unknown", "unknown"))

                    timeout_type = "TIMEOUT"
                    failure = getattr(attrs, "failure", None)
                    if failure:
                        timeout_type = getattr(failure, "message", "TIMEOUT")

                    errors.append(
                        WorkflowError(
                            event_id=event.event_id,
                            event_type="ACTIVITY_TASK_TIMED_OUT",
                            event_time=event_time,
                            error_message=timeout_type,
                            activity_type=activity_info[0],
                            activity_id=activity_info[1],
                        )
                    )

            elif type_name == "EVENT_TYPE_WORKFLOW_EXECUTION_FAILED":
                attrs = getattr(event, "workflow_execution_failed_event_attributes", None)
                if attrs:
                    failure = getattr(attrs, "failure", None)
                    msg, err_type, stack, cause = _extract_failure_details(failure)
                    errors.append(
                        WorkflowError(
                            event_id=event.event_id,
                            event_type="WORKFLOW_EXECUTION_FAILED",
                            event_time=event_time,
                            error_message=msg,
                            error_type=err_type,
                            stack_trace=stack,
                            cause=cause,
                        )
                    )

            elif type_name == "EVENT_TYPE_WORKFLOW_EXECUTION_TIMED_OUT":
                attrs = getattr(event, "workflow_execution_timed_out_event_attributes", None)
                retry_state = ""
                if attrs:
                    rs = getattr(attrs, "retry_state", None)
                    retry_state = str(rs) if rs else ""

                errors.append(
                    WorkflowError(
                        event_id=event.event_id,
                        event_type="WORKFLOW_EXECUTION_TIMED_OUT",
                        event_time=event_time,
                        error_message=f"Workflow timed out. Retry state: {retry_state}",
                    )
                )

            elif type_name == "EVENT_TYPE_WORKFLOW_EXECUTION_CANCELED":
                attrs = getattr(event, "workflow_execution_canceled_event_attributes", None)
                details = ""
                if attrs:
                    d = getattr(attrs, "details", None)
                    if d:
                        details = _extract_payload_data(d)

                errors.append(
                    WorkflowError(
                        event_id=event.event_id,
                        event_type="WORKFLOW_EXECUTION_CANCELED",
                        event_time=event_time,
                        error_message=f"Workflow was canceled. Details: {details}",
                    )
                )

            elif type_name == "EVENT_TYPE_WORKFLOW_EXECUTION_TERMINATED":
                attrs = getattr(event, "workflow_execution_terminated_event_attributes", None)
                reason = "No reason provided"
                if attrs:
                    r = getattr(attrs, "reason", None)
                    if r:
                        reason = r

                errors.append(
                    WorkflowError(
                        event_id=event.event_id,
                        event_type="WORKFLOW_EXECUTION_TERMINATED",
                        event_time=event_time,
                        error_message=f"Workflow was terminated. Reason: {reason}",
                    )
                )

            elif type_name == "EVENT_TYPE_CHILD_WORKFLOW_EXECUTION_FAILED":
                attrs = getattr(event, "child_workflow_execution_failed_event_attributes", None)
                if attrs:
                    failure = getattr(attrs, "failure", None)
                    msg, err_type, stack, cause = _extract_failure_details(failure)
                    wf_exec = getattr(attrs, "workflow_execution", None)
                    child_id = getattr(wf_exec, "workflow_id", "unknown") if wf_exec else "unknown"

                    errors.append(
                        WorkflowError(
                            event_id=event.event_id,
                            event_type="CHILD_WORKFLOW_EXECUTION_FAILED",
                            event_time=event_time,
                            error_message=msg,
                            error_type=err_type,
                            stack_trace=stack,
                            cause=f"Child workflow: {child_id}. {cause or ''}".strip(),
                        )
                    )

    except Exception as e:
        return f"Error fetching workflow errors: {e}"

    if not errors:
        return f"No errors found for workflow {workflow_id}. The workflow may have completed successfully."

    lines = [
        f"Errors for Workflow: {workflow_id}",
        f"Run ID: {run_id or 'latest'}",
        f"Found {len(errors)} error event(s)",
        "",
    ]

    for err in errors:
        time_str = err.event_time.strftime("%H:%M:%S.%f")[:-3] if err.event_time else "N/A"
        lines.append(f"[{err.event_id:4d}] {time_str} | {err.event_type}")

        if err.activity_type:
            lines.append(f"       Activity: {err.activity_type} (id={err.activity_id})")
        if err.attempt:
            lines.append(f"       Attempt: {err.attempt}")
        if err.error_type:
            lines.append(f"       Error Type: {err.error_type}")
        lines.append(f"       Message: {err.error_message}")
        if err.cause:
            lines.append(f"       Cause: {err.cause}")
        if err.stack_trace:
            lines.append("       Stack Trace:")
            for line in err.stack_trace.split("\n")[:10]:
                lines.append(f"         {line}")
            if err.stack_trace.count("\n") > 10:
                lines.append("         ... (truncated)")
        lines.append("")

    return "\n".join(lines)


@mcp.tool()
async def analyze_workflow_timeline(
    workflow_id: str,
    run_id: str = "",
) -> str:
    """Analyze the timing of a workflow execution to identify bottlenecks.

    Provides detailed timing analysis for each activity including queue time,
    execution time, and identifies the slowest activities.

    Args:
        workflow_id: The workflow ID
        run_id: Optional run ID (uses latest run if not specified)
    """
    client: Client = await _get_client_manager().get_client()
    handle = client.get_workflow_handle(workflow_id, run_id=run_id if run_id else None)

    workflow_type = "unknown"
    workflow_start: datetime | None = None
    workflow_end: datetime | None = None

    activities: dict[int, ActivityTiming] = {}
    started_events: dict[int, tuple[int, datetime | None]] = {}

    try:
        async for event in handle.fetch_history_events():
            event_time: datetime | None = None
            raw_time = getattr(event, "event_time", None)
            if raw_time is not None:
                if hasattr(raw_time, "ToDatetime"):
                    event_time = raw_time.ToDatetime(tzinfo=UTC)
                elif isinstance(raw_time, datetime):
                    event_time = raw_time

            event_type_enum = getattr(event, "event_type", None)
            if event_type_enum is None:
                continue
            type_name = (
                event_type_enum.name if hasattr(event_type_enum, "name") else str(event_type_enum)
            )

            if type_name == "EVENT_TYPE_WORKFLOW_EXECUTION_STARTED":
                attrs = getattr(event, "workflow_execution_started_event_attributes", None)
                if attrs:
                    wf_type = getattr(attrs, "workflow_type", None)
                    workflow_type = getattr(wf_type, "name", "unknown") if wf_type else "unknown"
                workflow_start = event_time

            elif type_name in (
                "EVENT_TYPE_WORKFLOW_EXECUTION_COMPLETED",
                "EVENT_TYPE_WORKFLOW_EXECUTION_FAILED",
                "EVENT_TYPE_WORKFLOW_EXECUTION_TIMED_OUT",
                "EVENT_TYPE_WORKFLOW_EXECUTION_CANCELED",
                "EVENT_TYPE_WORKFLOW_EXECUTION_TERMINATED",
            ):
                workflow_end = event_time

            elif type_name == "EVENT_TYPE_ACTIVITY_TASK_SCHEDULED":
                attrs = getattr(event, "activity_task_scheduled_event_attributes", None)
                if attrs:
                    activity_type = getattr(attrs, "activity_type", None)
                    activity_name = getattr(activity_type, "name", "unknown") if activity_type else "unknown"
                    activity_id = getattr(attrs, "activity_id", "unknown")

                    activities[event.event_id] = ActivityTiming(
                        activity_id=activity_id,
                        activity_type=activity_name,
                        scheduled_event_id=event.event_id,
                        scheduled_time=event_time,
                        status="scheduled",
                    )

            elif type_name == "EVENT_TYPE_ACTIVITY_TASK_STARTED":
                attrs = getattr(event, "activity_task_started_event_attributes", None)
                if attrs:
                    scheduled_id = getattr(attrs, "scheduled_event_id", None)
                    if scheduled_id and scheduled_id in activities:
                        activity = activities[scheduled_id]
                        activity.started_event_id = event.event_id
                        activity.started_time = event_time
                        activity.status = "running"
                        attempt = getattr(attrs, "attempt", 1)
                        activity.attempt = attempt if attempt else 1

                        if activity.scheduled_time and event_time:
                            queue_ms = (event_time - activity.scheduled_time).total_seconds() * 1000
                            activity.queue_duration_ms = queue_ms

                    started_events[event.event_id] = (scheduled_id or 0, event_time)

            elif type_name == "EVENT_TYPE_ACTIVITY_TASK_COMPLETED":
                attrs = getattr(event, "activity_task_completed_event_attributes", None)
                if attrs:
                    scheduled_id = getattr(attrs, "scheduled_event_id", None)
                    if scheduled_id and scheduled_id in activities:
                        activity = activities[scheduled_id]
                        activity.completed_event_id = event.event_id
                        activity.completed_time = event_time
                        activity.status = "completed"

                        if activity.started_time and event_time:
                            exec_ms = (event_time - activity.started_time).total_seconds() * 1000
                            activity.execution_duration_ms = exec_ms

                        if activity.scheduled_time and event_time:
                            total_ms = (event_time - activity.scheduled_time).total_seconds() * 1000
                            activity.total_duration_ms = total_ms

            elif type_name == "EVENT_TYPE_ACTIVITY_TASK_FAILED":
                attrs = getattr(event, "activity_task_failed_event_attributes", None)
                if attrs:
                    scheduled_id = getattr(attrs, "scheduled_event_id", None)
                    if scheduled_id and scheduled_id in activities:
                        activity = activities[scheduled_id]
                        activity.completed_event_id = event.event_id
                        activity.completed_time = event_time
                        activity.status = "failed"

                        if activity.started_time and event_time:
                            exec_ms = (event_time - activity.started_time).total_seconds() * 1000
                            activity.execution_duration_ms = exec_ms

                        if activity.scheduled_time and event_time:
                            total_ms = (event_time - activity.scheduled_time).total_seconds() * 1000
                            activity.total_duration_ms = total_ms

            elif type_name == "EVENT_TYPE_ACTIVITY_TASK_TIMED_OUT":
                attrs = getattr(event, "activity_task_timed_out_event_attributes", None)
                if attrs:
                    scheduled_id = getattr(attrs, "scheduled_event_id", None)
                    if scheduled_id and scheduled_id in activities:
                        activity = activities[scheduled_id]
                        activity.completed_event_id = event.event_id
                        activity.completed_time = event_time
                        activity.status = "timed_out"

                        if activity.scheduled_time and event_time:
                            total_ms = (event_time - activity.scheduled_time).total_seconds() * 1000
                            activity.total_duration_ms = total_ms

    except Exception as e:
        return f"Error analyzing workflow timeline: {e}"

    activity_list = list(activities.values())

    total_duration_ms: float | None = None
    if workflow_start and workflow_end:
        total_duration_ms = (workflow_end - workflow_start).total_seconds() * 1000

    slowest_activity: str | None = None
    slowest_duration: float | None = None
    total_queue_time: float = 0
    total_exec_time: float = 0

    for a in activity_list:
        if a.total_duration_ms is not None and (
            slowest_duration is None or a.total_duration_ms > slowest_duration
        ):
            slowest_duration = a.total_duration_ms
            slowest_activity = a.activity_type
        if a.queue_duration_ms:
            total_queue_time += a.queue_duration_ms
        if a.execution_duration_ms:
            total_exec_time += a.execution_duration_ms

    timeline = WorkflowTimeline(
        workflow_id=workflow_id,
        run_id=run_id or "latest",
        workflow_type=workflow_type,
        start_time=workflow_start,
        end_time=workflow_end,
        total_duration_ms=total_duration_ms,
        activities=activity_list,
        slowest_activity=slowest_activity,
        slowest_activity_duration_ms=slowest_duration,
        total_queue_time_ms=total_queue_time if total_queue_time > 0 else None,
        total_execution_time_ms=total_exec_time if total_exec_time > 0 else None,
    )

    def _fmt_duration(ms: float | None) -> str:
        if ms is None:
            return "N/A"
        if ms < 1000:
            return f"{ms:.1f}ms"
        elif ms < 60000:
            return f"{ms / 1000:.2f}s"
        else:
            return f"{ms / 60000:.2f}m"

    lines = [
        f"Timeline Analysis for Workflow: {timeline.workflow_id}",
        f"Run ID: {timeline.run_id}",
        f"Type: {timeline.workflow_type}",
        "",
        "=== Summary ===",
    ]

    if timeline.start_time:
        lines.append(f"Start Time: {timeline.start_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} UTC")
    if timeline.end_time:
        lines.append(f"End Time: {timeline.end_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} UTC")
    lines.append(f"Total Duration: {_fmt_duration(timeline.total_duration_ms)}")
    lines.append(f"Total Activities: {len(timeline.activities)}")

    if timeline.slowest_activity:
        lines.append(
            f"Slowest Activity: {timeline.slowest_activity} "
            f"({_fmt_duration(timeline.slowest_activity_duration_ms)})"
        )
    if timeline.total_queue_time_ms:
        lines.append(f"Total Queue Time: {_fmt_duration(timeline.total_queue_time_ms)}")
    if timeline.total_execution_time_ms:
        lines.append(f"Total Execution Time: {_fmt_duration(timeline.total_execution_time_ms)}")

    if activity_list:
        lines.append("")
        lines.append("=== Activity Breakdown ===")
        lines.append(
            f"{'Activity':<30} {'Status':<12} {'Queue':<10} {'Exec':<10} {'Total':<10} {'Attempt'}"
        )
        lines.append("-" * 85)

        sorted_activities = sorted(
            activity_list,
            key=lambda x: x.total_duration_ms or 0,
            reverse=True,
        )

        for a in sorted_activities:
            name = a.activity_type[:28] + ".." if len(a.activity_type) > 30 else a.activity_type
            lines.append(
                f"{name:<30} {a.status:<12} "
                f"{_fmt_duration(a.queue_duration_ms):<10} "
                f"{_fmt_duration(a.execution_duration_ms):<10} "
                f"{_fmt_duration(a.total_duration_ms):<10} "
                f"{a.attempt}"
            )

    if not activity_list:
        lines.append("")
        lines.append("No activities found in this workflow.")

    return "\n".join(lines)


def main() -> None:
    """Run the MCP server."""
    logging.basicConfig(level=logging.INFO)
    logger.info("Starting Temporal MCP server...")
    mcp.run()


if __name__ == "__main__":
    main()
