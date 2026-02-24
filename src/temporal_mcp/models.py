"""Pydantic models for Temporal MCP responses."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class WorkflowStatus(StrEnum):
    """Workflow execution status."""

    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELED = "CANCELED"
    TERMINATED = "TERMINATED"
    CONTINUED_AS_NEW = "CONTINUED_AS_NEW"
    TIMED_OUT = "TIMED_OUT"
    UNKNOWN = "UNKNOWN"


class WorkflowSummary(BaseModel):
    """Summary of a workflow execution for listing."""

    workflow_id: str = Field(description="Unique workflow identifier")
    run_id: str = Field(description="Unique run identifier")
    workflow_type: str = Field(description="Name of the workflow type")
    status: WorkflowStatus = Field(description="Current execution status")
    start_time: datetime | None = Field(
        default=None, description="When the workflow started"
    )
    close_time: datetime | None = Field(
        default=None, description="When the workflow closed (if applicable)"
    )
    task_queue: str = Field(description="Task queue the workflow runs on")


class PendingActivity(BaseModel):
    """Information about a pending activity."""

    activity_id: str = Field(description="Activity identifier")
    activity_type: str = Field(description="Name of the activity type")
    state: str = Field(description="Current activity state")
    attempt: int = Field(description="Current attempt number")
    last_failure: str | None = Field(
        default=None, description="Last failure message if any"
    )


class WorkflowDescription(BaseModel):
    """Detailed description of a workflow execution."""

    workflow_id: str = Field(description="Unique workflow identifier")
    run_id: str = Field(description="Unique run identifier")
    workflow_type: str = Field(description="Name of the workflow type")
    status: WorkflowStatus = Field(description="Current execution status")
    start_time: datetime | None = Field(
        default=None, description="When the workflow started"
    )
    close_time: datetime | None = Field(
        default=None, description="When the workflow closed (if applicable)"
    )
    execution_time: datetime | None = Field(
        default=None, description="When the workflow first started executing"
    )
    task_queue: str = Field(description="Task queue the workflow runs on")
    history_length: int = Field(description="Number of events in history")
    pending_activities: list[PendingActivity] = Field(
        default_factory=list, description="List of pending activities"
    )
    memo: dict[str, str] = Field(
        default_factory=dict, description="Workflow memo fields"
    )
    search_attributes: dict[str, str] = Field(
        default_factory=dict, description="Workflow search attributes"
    )


class HistoryEvent(BaseModel):
    """A single event in workflow history."""

    event_id: int = Field(description="Event sequence number")
    event_time: datetime | None = Field(description="When the event occurred")
    event_type: str = Field(description="Type of the event")
    details: str = Field(description="Human-readable event details")


class WorkflowHistory(BaseModel):
    """Workflow history for debugging."""

    workflow_id: str = Field(description="Unique workflow identifier")
    run_id: str = Field(description="Unique run identifier")
    events: list[HistoryEvent] = Field(description="List of history events")
    total_events: int = Field(description="Total number of events in history")
    truncated: bool = Field(
        default=False, description="Whether the history was truncated"
    )


class EventPayload(BaseModel):
    """Payload data from a workflow event."""

    event_id: int = Field(description="Event sequence number")
    event_type: str = Field(description="Type of the event")
    event_time: datetime | None = Field(default=None, description="When the event occurred")
    payload_type: str = Field(description="Type of payload (input, output, result, etc.)")
    data: str = Field(description="JSON-serialized payload data")
    related_event_id: int | None = Field(
        default=None, description="Related event ID (e.g., scheduled event for completion)"
    )


class WorkflowError(BaseModel):
    """Error information from a workflow event."""

    event_id: int = Field(description="Event sequence number")
    event_type: str = Field(description="Type of the error event")
    event_time: datetime | None = Field(default=None, description="When the error occurred")
    error_message: str = Field(description="Error message")
    error_type: str | None = Field(default=None, description="Error/exception type")
    stack_trace: str | None = Field(default=None, description="Stack trace if available")
    activity_type: str | None = Field(
        default=None, description="Activity type if this is an activity failure"
    )
    activity_id: str | None = Field(
        default=None, description="Activity ID if this is an activity failure"
    )
    attempt: int | None = Field(default=None, description="Retry attempt number")
    cause: str | None = Field(default=None, description="Cause chain for nested failures")


class ActivityTiming(BaseModel):
    """Timing information for a single activity execution."""

    activity_id: str = Field(description="Activity identifier")
    activity_type: str = Field(description="Name of the activity type")
    scheduled_event_id: int = Field(description="Event ID when activity was scheduled")
    started_event_id: int | None = Field(
        default=None, description="Event ID when activity started"
    )
    completed_event_id: int | None = Field(
        default=None, description="Event ID when activity completed/failed"
    )
    scheduled_time: datetime | None = Field(
        default=None, description="When the activity was scheduled"
    )
    started_time: datetime | None = Field(
        default=None, description="When the activity started executing"
    )
    completed_time: datetime | None = Field(
        default=None, description="When the activity completed or failed"
    )
    queue_duration_ms: float | None = Field(
        default=None, description="Time spent waiting in queue (ms)"
    )
    execution_duration_ms: float | None = Field(
        default=None, description="Time spent executing (ms)"
    )
    total_duration_ms: float | None = Field(
        default=None, description="Total time from scheduled to completion (ms)"
    )
    status: str = Field(description="Activity status (scheduled, running, completed, failed)")
    attempt: int = Field(default=1, description="Attempt number")


class WorkflowTimeline(BaseModel):
    """Timeline analysis of a workflow execution."""

    workflow_id: str = Field(description="Unique workflow identifier")
    run_id: str = Field(description="Unique run identifier")
    workflow_type: str = Field(description="Name of the workflow type")
    start_time: datetime | None = Field(default=None, description="Workflow start time")
    end_time: datetime | None = Field(default=None, description="Workflow end time")
    total_duration_ms: float | None = Field(
        default=None, description="Total workflow duration (ms)"
    )
    activities: list[ActivityTiming] = Field(
        default_factory=list, description="Timing for each activity"
    )
    slowest_activity: str | None = Field(
        default=None, description="Name of the slowest activity"
    )
    slowest_activity_duration_ms: float | None = Field(
        default=None, description="Duration of the slowest activity (ms)"
    )
    total_queue_time_ms: float | None = Field(
        default=None, description="Total time activities spent in queue (ms)"
    )
    total_execution_time_ms: float | None = Field(
        default=None, description="Total time spent executing activities (ms)"
    )
