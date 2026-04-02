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
