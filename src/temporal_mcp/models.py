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
