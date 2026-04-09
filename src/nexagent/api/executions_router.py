"""Execution REST + WebSocket API endpoints."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from nexagent.database import async_session, get_db
from nexagent.engine.master_runner import run_workflow
from nexagent.schemas.executions import (
    ExecuteRequest,
    ExecutionEvent,
    ExecutionList,
    ExecutionRead,
    ExecutionSummary,
    TimelineLane,
    TimelineResponse,
    TimelineStep,
)
from nexagent.services.execution_service import (
    ExecutionNotFoundError,
    complete_execution,
    create_execution,
    delete_execution,
    get_execution,
    list_executions,
)
from nexagent.services.workflow_service import (
    WorkflowNotFoundError,
    get_workflow,
    validate_workflow,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["executions"])

# In-memory event queues for WebSocket streaming
_event_queues: dict[uuid.UUID, list[asyncio.Queue]] = {}


def _publish_event(execution_id: uuid.UUID, event: ExecutionEvent) -> None:
    """Push an event to all connected WebSocket clients for this execution."""
    queues = _event_queues.get(execution_id, [])
    for q in queues:
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            pass


# ---------------------------------------------------------------------------
# S5.6: Execute + CRUD
# ---------------------------------------------------------------------------


async def _run_execution_background(
    execution_id: uuid.UUID,
    workflow_id: uuid.UUID,
    task_input: str,
) -> None:
    """Background task that runs the workflow and persists results."""
    try:
        async with async_session() as db:
            workflow = await get_workflow(db, workflow_id)
            state = await run_workflow(db, workflow, task_input, execution_id=execution_id)
            await db.commit()

            _publish_event(execution_id, ExecutionEvent(
                event_type="execution_completed" if state.status == "completed" else "execution_failed",
                data={"final_output": state.final_output, "status": state.status},
                timestamp=datetime.now(timezone.utc),
            ))
    except Exception as e:
        logger.error("Execution %s failed: %s", execution_id, e)
        try:
            async with async_session() as db:
                await complete_execution(
                    db, execution_id, status="failed", error_message=str(e),
                )
                await db.commit()
        except Exception:
            logger.exception("Failed to record execution failure")

        _publish_event(execution_id, ExecutionEvent(
            event_type="execution_failed",
            data={"error": str(e)},
            timestamp=datetime.now(timezone.utc),
        ))
    finally:
        # Clean up event queues after a short delay
        await asyncio.sleep(5)
        _event_queues.pop(execution_id, None)


@router.post("/api/v1/execute", status_code=202)
async def execute_workflow(
    data: ExecuteRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Start a workflow execution asynchronously."""
    # Validate workflow exists and is ready
    try:
        validation = await validate_workflow(db, data.workflow_id)
    except WorkflowNotFoundError:
        raise HTTPException(status_code=404, detail=f"Workflow {data.workflow_id} not found")

    if not validation.valid:
        raise HTTPException(status_code=422, detail={"errors": validation.errors})

    # Create execution record
    exc = await create_execution(db, data.workflow_id, data.task_input)
    await db.commit()

    # Set up event queue for this execution
    _event_queues[exc.id] = []

    # Launch background task
    asyncio.create_task(_run_execution_background(exc.id, data.workflow_id, data.task_input))

    return {
        "execution_id": str(exc.id),
        "status": "pending",
        "message": "Execution started",
    }


@router.get("/api/v1/executions", response_model=ExecutionList)
async def list_executions_endpoint(
    workflow_id: uuid.UUID | None = Query(None),
    status: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> ExecutionList:
    """List executions with filtering and pagination."""
    items, total = await list_executions(
        db, workflow_id=workflow_id, status=status, offset=offset, limit=limit,
    )
    return ExecutionList(
        items=[
            ExecutionSummary(
                id=e.id,
                workflow_id=e.workflow_id,
                task_input=e.task_input,
                status=e.status,
                total_tokens=e.total_tokens,
                total_cost_usd=float(e.total_cost_usd) if e.total_cost_usd is not None else None,
                started_at=e.started_at,
                finished_at=e.finished_at,
                created_at=e.created_at,
                lane_count=len(e.lanes) if e.lanes else 0,
            )
            for e in items
        ],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/api/v1/executions/{execution_id}", response_model=ExecutionRead)
async def get_execution_endpoint(
    execution_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ExecutionRead:
    """Get full execution detail with lanes and steps."""
    try:
        exc = await get_execution(db, execution_id)
    except ExecutionNotFoundError:
        raise HTTPException(status_code=404, detail=f"Execution {execution_id} not found")
    return ExecutionRead.model_validate(exc)


@router.post("/api/v1/executions/{execution_id}/cancel")
async def cancel_execution(
    execution_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Cancel a running execution."""
    try:
        exc = await get_execution(db, execution_id)
    except ExecutionNotFoundError:
        raise HTTPException(status_code=404, detail=f"Execution {execution_id} not found")

    if exc.status not in ("pending", "running"):
        raise HTTPException(status_code=409, detail=f"Cannot cancel execution in status '{exc.status}'")

    exc.status = "cancelled"
    exc.finished_at = datetime.now(timezone.utc)
    await db.commit()

    _publish_event(execution_id, ExecutionEvent(
        event_type="execution_failed",
        data={"status": "cancelled"},
        timestamp=datetime.now(timezone.utc),
    ))

    return {"status": "cancelled"}


@router.delete("/api/v1/executions/{execution_id}", status_code=204, response_model=None)
async def delete_execution_endpoint(
    execution_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Hard-delete an execution and all its lanes/steps."""
    try:
        await delete_execution(db, execution_id)
        await db.commit()
    except ExecutionNotFoundError:
        raise HTTPException(status_code=404, detail=f"Execution {execution_id} not found")


# ---------------------------------------------------------------------------
# S6.3: Timeline API
# ---------------------------------------------------------------------------


@router.get("/api/v1/executions/{execution_id}/timeline", response_model=TimelineResponse)
async def get_execution_timeline(
    execution_id: uuid.UUID,
    include_data: bool = Query(False),
    db: AsyncSession = Depends(get_db),
) -> TimelineResponse:
    """Return the lane-based timeline for the guitar-view frontend."""
    try:
        exc = await get_execution(db, execution_id)
    except ExecutionNotFoundError:
        raise HTTPException(status_code=404, detail=f"Execution {execution_id} not found")

    lanes: list[TimelineLane] = []
    for lane in sorted(exc.lanes, key=lambda l: l.lane_index):
        steps: list[TimelineStep] = []
        for step in sorted(lane.steps, key=lambda s: s.step_index):
            ts = TimelineStep(
                step_index=step.step_index,
                step_type=step.step_type,
                status=step.status,
                duration_ms=step.duration_ms,
                started_at=step.started_at,
                finished_at=step.finished_at,
                input_data=step.input_data if include_data else None,
                output_data=step.output_data if include_data else None,
            )
            steps.append(ts)
        lanes.append(TimelineLane(
            lane_index=lane.lane_index,
            actor_type=lane.actor_type,
            actor_name=lane.actor_name,
            status=lane.status,
            started_at=lane.started_at,
            finished_at=lane.finished_at,
            steps=steps,
        ))

    return TimelineResponse(
        execution_id=exc.id,
        status=exc.status,
        task_input=exc.task_input,
        final_output=exc.final_output,
        total_tokens=exc.total_tokens,
        total_cost_usd=float(exc.total_cost_usd) if exc.total_cost_usd is not None else None,
        lanes=lanes,
    )


# ---------------------------------------------------------------------------
# S6.4: WebSocket Live Execution Stream
# ---------------------------------------------------------------------------


@router.websocket("/api/v1/executions/{execution_id}/live")
async def execution_live_stream(
    websocket: WebSocket,
    execution_id: uuid.UUID,
) -> None:
    """WebSocket endpoint for real-time execution updates."""
    await websocket.accept()

    # Create a queue for this client
    queue: asyncio.Queue[ExecutionEvent] = asyncio.Queue(maxsize=100)
    if execution_id not in _event_queues:
        _event_queues[execution_id] = []
    _event_queues[execution_id].append(queue)

    try:
        # Send current state as catch-up
        async with async_session() as db:
            try:
                exc = await get_execution(db, execution_id)
                await websocket.send_json({
                    "event_type": "state_sync",
                    "data": {
                        "status": exc.status,
                        "lane_count": len(exc.lanes),
                    },
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            except ExecutionNotFoundError:
                await websocket.send_json({
                    "event_type": "error",
                    "data": {"message": "Execution not found"},
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                await websocket.close()
                return

        # Stream events
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30.0)
                await websocket.send_json(event.model_dump(mode="json"))
                if event.event_type in ("execution_completed", "execution_failed"):
                    break
            except asyncio.TimeoutError:
                # Send heartbeat
                await websocket.send_json({
                    "event_type": "heartbeat",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
    except WebSocketDisconnect:
        pass
    finally:
        # Remove this client's queue
        queues = _event_queues.get(execution_id, [])
        if queue in queues:
            queues.remove(queue)
