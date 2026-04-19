"""Execution CRUD + tracker service — records every step of an execution."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from nexagent.models.execution import Execution
from nexagent.models.execution_lane import ExecutionLane
from nexagent.models.execution_step import ExecutionStep

# ---------------------------------------------------------------------------
# Cost estimation: USD per 1K tokens (input/output combined for simplicity)
# Override via config in the future.
# ---------------------------------------------------------------------------
MODEL_COST_PER_1K: dict[str, float] = {
    "gpt-4o": 0.005,
    "gpt-4o-mini": 0.00015,
    "gpt-4-turbo": 0.01,
    "gpt-3.5-turbo": 0.0005,
    "claude-3-5-sonnet-20241022": 0.006,
    "claude-3-haiku-20240307": 0.00025,
}

DEFAULT_COST_PER_1K = 0.002


class ExecutionServiceError(Exception):
    pass


class ExecutionNotFoundError(ExecutionServiceError):
    pass


# ---------------------------------------------------------------------------
# Execution CRUD
# ---------------------------------------------------------------------------


async def create_execution(
    db: AsyncSession,
    workflow_id: uuid.UUID | None,
    task_input: str,
) -> Execution:
    """Create a new execution record and the master lane (index 0)."""
    exc = Execution(
        workflow_id=workflow_id,
        task_input=task_input,
        status="pending",
    )
    db.add(exc)
    await db.flush()
    await db.refresh(exc)
    return exc


async def get_execution(db: AsyncSession, execution_id: uuid.UUID) -> Execution:
    """Load a full execution with lanes and steps."""
    result = await db.execute(
        select(Execution)
        .options(
            selectinload(Execution.lanes).selectinload(ExecutionLane.steps)
        )
        .where(Execution.id == execution_id)
    )
    exc = result.scalar_one_or_none()
    if exc is None:
        raise ExecutionNotFoundError(f"Execution {execution_id} not found")
    return exc


async def list_executions(
    db: AsyncSession,
    *,
    workflow_id: uuid.UUID | None = None,
    status: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[Execution], int]:
    """List executions with optional filters."""
    query = select(Execution).options(selectinload(Execution.lanes))
    count_query = select(func.count()).select_from(Execution)

    if workflow_id is not None:
        query = query.where(Execution.workflow_id == workflow_id)
        count_query = count_query.where(Execution.workflow_id == workflow_id)
    if status is not None:
        query = query.where(Execution.status == status)
        count_query = count_query.where(Execution.status == status)

    total = (await db.execute(count_query)).scalar_one()
    query = query.order_by(Execution.created_at.desc()).offset(offset).limit(limit)
    items = list((await db.execute(query)).scalars().unique().all())
    return items, total


async def delete_execution(db: AsyncSession, execution_id: uuid.UUID) -> None:
    """Hard-delete an execution (cascades to lanes and steps)."""
    exc = await get_execution(db, execution_id)
    await db.delete(exc)
    await db.flush()


# ---------------------------------------------------------------------------
# Tracker: lane + step recording
# ---------------------------------------------------------------------------


async def start_execution(db: AsyncSession, execution_id: uuid.UUID) -> Execution:
    """Mark execution as running."""
    exc = await get_execution(db, execution_id)
    exc.status = "running"
    exc.started_at = datetime.now(timezone.utc)
    await db.flush()
    return exc


async def create_lane(
    db: AsyncSession,
    execution_id: uuid.UUID,
    lane_index: int,
    actor_type: str,
    actor_id: uuid.UUID | None,
    actor_name: str,
) -> ExecutionLane:
    """Create a new lane for an execution."""
    lane = ExecutionLane(
        execution_id=execution_id,
        lane_index=lane_index,
        actor_type=actor_type,
        actor_id=actor_id,
        actor_name=actor_name,
        status="pending",
    )
    db.add(lane)
    await db.flush()
    await db.refresh(lane)
    return lane


async def start_lane(db: AsyncSession, lane_id: uuid.UUID) -> ExecutionLane:
    """Mark a lane as running."""
    lane = await db.get(ExecutionLane, lane_id)
    if lane is None:
        raise ExecutionNotFoundError(f"Lane {lane_id} not found")
    lane.status = "running"
    lane.started_at = datetime.now(timezone.utc)
    await db.flush()
    return lane


async def complete_lane(
    db: AsyncSession,
    lane_id: uuid.UUID,
    status: str = "completed",
) -> ExecutionLane:
    """Mark a lane as completed or failed."""
    lane = await db.get(ExecutionLane, lane_id)
    if lane is None:
        raise ExecutionNotFoundError(f"Lane {lane_id} not found")
    lane.status = status
    lane.finished_at = datetime.now(timezone.utc)
    await db.flush()
    return lane


async def record_step(
    db: AsyncSession,
    lane_id: uuid.UUID,
    step_index: int,
    step_type: str,
    *,
    input_data: dict[str, Any] | None = None,
    output_data: dict[str, Any] | None = None,
    model_used: str | None = None,
    tokens_prompt: int | None = None,
    tokens_completion: int | None = None,
    duration_ms: int | None = None,
    status: str = "completed",
    error_message: str | None = None,
) -> ExecutionStep:
    """Record a step within a lane."""
    now = datetime.now(timezone.utc)
    step = ExecutionStep(
        lane_id=lane_id,
        step_index=step_index,
        step_type=step_type,
        input_data=input_data,
        output_data=output_data,
        model_used=model_used,
        tokens_prompt=tokens_prompt,
        tokens_completion=tokens_completion,
        duration_ms=duration_ms,
        status=status,
        error_message=error_message,
        started_at=now,
        finished_at=now if status != "running" else None,
    )
    db.add(step)
    await db.flush()
    await db.refresh(step)
    return step


async def complete_execution(
    db: AsyncSession,
    execution_id: uuid.UUID,
    *,
    final_output: str | None = None,
    status: str = "completed",
    error_message: str | None = None,
    emit_buffer: list[dict[str, Any]] | None = None,
) -> Execution:
    """Finalize an execution — aggregate tokens and cost via SQL."""
    # Aggregate tokens directly from steps (avoids stale identity map)
    from sqlalchemy import func as sa_func

    token_stmt = (
        select(
            sa_func.coalesce(sa_func.sum(ExecutionStep.tokens_prompt), 0),
            sa_func.coalesce(sa_func.sum(ExecutionStep.tokens_completion), 0),
        )
        .join(ExecutionLane, ExecutionStep.lane_id == ExecutionLane.id)
        .where(ExecutionLane.execution_id == execution_id)
    )
    row = (await db.execute(token_stmt)).one()
    total_prompt = int(row[0])
    total_completion = int(row[1])
    total_tokens = total_prompt + total_completion

    # Estimate cost using model-specific rates
    cost_stmt = (
        select(
            ExecutionStep.model_used,
            sa_func.coalesce(sa_func.sum(ExecutionStep.tokens_prompt), 0),
            sa_func.coalesce(sa_func.sum(ExecutionStep.tokens_completion), 0),
        )
        .join(ExecutionLane, ExecutionStep.lane_id == ExecutionLane.id)
        .where(ExecutionLane.execution_id == execution_id)
        .group_by(ExecutionStep.model_used)
    )
    cost_rows = (await db.execute(cost_stmt)).all()
    total_cost = 0.0
    for model, t_prompt, t_completion in cost_rows:
        rate = MODEL_COST_PER_1K.get(model or "", DEFAULT_COST_PER_1K)
        total_cost += ((int(t_prompt) + int(t_completion)) / 1000.0) * rate

    # Update execution
    exc = await db.get(Execution, execution_id)
    if exc is None:
        raise ExecutionNotFoundError(f"Execution {execution_id} not found")
    exc.status = status
    exc.finished_at = datetime.now(timezone.utc)
    exc.total_tokens = total_tokens
    exc.total_cost_usd = round(total_cost, 6)
    if final_output is not None:
        exc.final_output = final_output
    if error_message is not None:
        exc.error_message = error_message
    if emit_buffer is not None:
        exc.emit_buffer = emit_buffer
    await db.flush()
    await db.refresh(exc)
    return exc
