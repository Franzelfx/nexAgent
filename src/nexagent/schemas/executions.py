"""Pydantic schemas for Execution, Timeline, and Cost tracking APIs."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Execution request/response
# ---------------------------------------------------------------------------


class ExecuteRequest(BaseModel):
    """Request to trigger a workflow execution."""

    workflow_id: uuid.UUID
    task_input: str = Field(..., min_length=1)


class ExecutionStepRead(BaseModel):
    """A single step within an execution lane."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    step_index: int
    step_type: str
    input_data: dict[str, Any] | None = None
    output_data: dict[str, Any] | None = None
    model_used: str | None = None
    tokens_prompt: int | None = None
    tokens_completion: int | None = None
    duration_ms: int | None = None
    status: str
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class ExecutionLaneRead(BaseModel):
    """A lane (actor timeline row) within an execution."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    lane_index: int
    actor_type: str
    actor_id: uuid.UUID | None = None
    actor_name: str
    status: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    steps: list[ExecutionStepRead] = []


class ExecutionRead(BaseModel):
    """Full execution detail with lanes."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workflow_id: uuid.UUID | None
    task_input: str
    final_output: str | None = None
    status: str
    error_message: str | None = None
    total_tokens: int = 0
    total_cost_usd: float | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime
    lanes: list[ExecutionLaneRead] = []


class ExecutionSummary(BaseModel):
    """Lightweight execution list item (no nested steps)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workflow_id: uuid.UUID | None
    task_input: str
    status: str
    total_tokens: int = 0
    total_cost_usd: float | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime
    lane_count: int = 0


class ExecutionList(BaseModel):
    """Paginated list of executions."""

    items: list[ExecutionSummary]
    total: int
    offset: int
    limit: int


# ---------------------------------------------------------------------------
# Timeline (guitar view)
# ---------------------------------------------------------------------------


class TimelineStep(BaseModel):
    """A step in the timeline view."""

    step_index: int
    step_type: str
    status: str
    duration_ms: int | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    # Only included when include_data=true
    input_data: dict[str, Any] | None = None
    output_data: dict[str, Any] | None = None


class TimelineLane(BaseModel):
    """A lane in the timeline view."""

    lane_index: int
    actor_type: str
    actor_name: str
    status: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    steps: list[TimelineStep] = []


class TimelineResponse(BaseModel):
    """Structured timeline for the guitar-view frontend."""

    execution_id: uuid.UUID
    status: str
    task_input: str
    final_output: str | None = None
    total_tokens: int = 0
    total_cost_usd: float | None = None
    lanes: list[TimelineLane] = []


# ---------------------------------------------------------------------------
# WebSocket events
# ---------------------------------------------------------------------------


class ExecutionEvent(BaseModel):
    """Real-time event pushed over WebSocket."""

    event_type: str  # lane_started, step_started, step_completed, lane_completed, execution_completed, execution_failed
    lane_index: int | None = None
    step_index: int | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime
