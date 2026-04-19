"""Orchestrator REST API endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from nexagent.database import get_db
from nexagent.schemas.orchestrators import (
    CapabilityMap,
    OrchestratorCreate,
    OrchestratorList,
    OrchestratorRead,
    OrchestratorUpdate,
)
from nexagent.services.orchestrator_service import (
    OrchestratorNotFoundError,
    add_sub_agent,
    bind_sub_agents,
    create_orchestrator,
    delete_orchestrator,
    get_orchestrator,
    list_orchestrators,
    remove_sub_agent,
    update_orchestrator,
)

router = APIRouter(prefix="/api/v1/orchestrators", tags=["orchestrators"])


@router.post("", response_model=OrchestratorRead, status_code=201)
async def create_orchestrator_endpoint(
    data: OrchestratorCreate,
    db: AsyncSession = Depends(get_db),
) -> OrchestratorRead:
    try:
        orch = await create_orchestrator(db, data)
        await db.commit()
        return OrchestratorRead.model_validate(orch)
    except OrchestratorNotFoundError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("", response_model=OrchestratorList)
async def list_orchestrators_endpoint(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    is_active: bool | None = Query(None),
    search: str | None = Query(None, max_length=255),
    db: AsyncSession = Depends(get_db),
) -> OrchestratorList:
    items, total = await list_orchestrators(
        db, offset=offset, limit=limit, is_active=is_active, search=search
    )
    return OrchestratorList(
        items=[OrchestratorRead.model_validate(o) for o in items],
        total=total, offset=offset, limit=limit,
    )


@router.get("/{orch_id}", response_model=OrchestratorRead)
async def get_orchestrator_endpoint(
    orch_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> OrchestratorRead:
    try:
        orch = await get_orchestrator(db, orch_id)
        return OrchestratorRead.model_validate(orch)
    except OrchestratorNotFoundError:
        raise HTTPException(status_code=404, detail=f"Orchestrator {orch_id} not found")


@router.put("/{orch_id}", response_model=OrchestratorRead)
async def update_orchestrator_endpoint(
    orch_id: uuid.UUID,
    data: OrchestratorUpdate,
    db: AsyncSession = Depends(get_db),
) -> OrchestratorRead:
    try:
        orch = await update_orchestrator(db, orch_id, data)
        await db.commit()
        return OrchestratorRead.model_validate(orch)
    except OrchestratorNotFoundError:
        raise HTTPException(status_code=404, detail=f"Orchestrator {orch_id} not found")


@router.delete("/{orch_id}", response_model=OrchestratorRead)
async def delete_orchestrator_endpoint(
    orch_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> OrchestratorRead:
    try:
        orch = await delete_orchestrator(db, orch_id)
        await db.commit()
        return OrchestratorRead.model_validate(orch)
    except OrchestratorNotFoundError:
        raise HTTPException(status_code=404, detail=f"Orchestrator {orch_id} not found")


# --- Sub-agent binding endpoints ---


@router.put("/{orch_id}/sub-agents", response_model=OrchestratorRead)
async def bind_sub_agents_endpoint(
    orch_id: uuid.UUID,
    sub_agent_ids: list[uuid.UUID],
    db: AsyncSession = Depends(get_db),
) -> OrchestratorRead:
    """Replace all sub-agent bindings."""
    try:
        orch = await bind_sub_agents(db, orch_id, sub_agent_ids)
        await db.commit()
        return OrchestratorRead.model_validate(orch)
    except OrchestratorNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{orch_id}/sub-agents/{sub_agent_id}", response_model=OrchestratorRead)
async def add_sub_agent_endpoint(
    orch_id: uuid.UUID,
    sub_agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> OrchestratorRead:
    try:
        orch = await add_sub_agent(db, orch_id, sub_agent_id)
        await db.commit()
        return OrchestratorRead.model_validate(orch)
    except OrchestratorNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{orch_id}/sub-agents/{sub_agent_id}", response_model=OrchestratorRead)
async def remove_sub_agent_endpoint(
    orch_id: uuid.UUID,
    sub_agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> OrchestratorRead:
    try:
        orch = await remove_sub_agent(db, orch_id, sub_agent_id)
        await db.commit()
        return OrchestratorRead.model_validate(orch)
    except OrchestratorNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


# --- Capability map endpoint ---


@router.get("/{orch_id}/capability-map", response_model=CapabilityMap)
async def get_capability_map_endpoint(
    orch_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> CapabilityMap:
    """Get the auto-generated capability map for an orchestrator."""
    from nexagent.engine.capability_map import build_capability_map

    try:
        return await build_capability_map(db, orch_id)
    except OrchestratorNotFoundError:
        raise HTTPException(status_code=404, detail=f"Orchestrator {orch_id} not found")


# --- Direct execute endpoint (Epic 5: canvas chat) ---


from pydantic import BaseModel, Field
from sqlalchemy import select as _select

from nexagent.models.workflow import Workflow
from nexagent.schemas.workflows import WorkflowCreate


class OrchestratorExecuteRequest(BaseModel):
    task_input: str = Field(..., min_length=1)


class OrchestratorExecuteResponse(BaseModel):
    execution_id: uuid.UUID
    workflow_id: uuid.UUID
    status: str = "pending"


async def _get_or_create_default_workflow(
    db: AsyncSession, orch_id: uuid.UUID
) -> Workflow:
    """Return the implicit canvas-bound workflow for this orchestrator, creating
    one on first use. Subsequent chat executions reuse the same workflow so the
    execution history is coherent per orchestrator."""
    from nexagent.services.workflow_service import create_workflow

    result = await db.execute(
        _select(Workflow).where(
            Workflow.orchestrator_id == orch_id,
            Workflow.is_active.is_(True),
        ).order_by(Workflow.created_at.asc()).limit(1)
    )
    wf = result.scalar_one_or_none()
    if wf is not None:
        return wf

    # Lazy-create a canvas-bound workflow
    orch = await get_orchestrator(db, orch_id)
    created = await create_workflow(
        db,
        WorkflowCreate(
            name=f"{orch.name} (canvas)",
            description="Auto-generated canvas-bound workflow",
            orchestrator_id=orch_id,
            graph_layout={},
        ),
    )
    await db.flush()
    return created


@router.post("/{orch_id}/execute", response_model=OrchestratorExecuteResponse, status_code=202)
async def execute_orchestrator_endpoint(
    orch_id: uuid.UUID,
    data: OrchestratorExecuteRequest,
    db: AsyncSession = Depends(get_db),
) -> OrchestratorExecuteResponse:
    """Execute this orchestrator directly, reusing its implicit workflow.

    Mirrors /api/v1/execute semantics but removes the workflow_id requirement
    from the frontend by auto-managing a canvas-bound workflow per orchestrator.
    """
    import asyncio
    from nexagent.api.executions_router import (
        _event_queues,
        _run_execution_background,
    )
    from nexagent.services.execution_service import create_execution

    try:
        wf = await _get_or_create_default_workflow(db, orch_id)
    except OrchestratorNotFoundError:
        raise HTTPException(status_code=404, detail=f"Orchestrator {orch_id} not found")

    exc = await create_execution(db, wf.id, data.task_input)
    await db.commit()

    _event_queues[exc.id] = []
    asyncio.create_task(_run_execution_background(exc.id, wf.id, data.task_input))

    return OrchestratorExecuteResponse(
        execution_id=exc.id, workflow_id=wf.id, status="pending"
    )
