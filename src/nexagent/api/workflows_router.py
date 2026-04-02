"""Workflow REST API endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from nexagent.database import get_db
from nexagent.schemas.workflows import (
    ValidationResult,
    WorkflowCreate,
    WorkflowGraphExport,
    WorkflowList,
    WorkflowRead,
    WorkflowUpdate,
)
from nexagent.services.workflow_service import (
    WorkflowNotFoundError,
    create_workflow,
    delete_workflow,
    export_graph,
    get_workflow,
    list_workflows,
    update_workflow,
    validate_workflow,
)

router = APIRouter(prefix="/api/v1/workflows", tags=["workflows"])


@router.post("", response_model=WorkflowRead, status_code=201)
async def create_workflow_endpoint(
    data: WorkflowCreate,
    db: AsyncSession = Depends(get_db),
) -> WorkflowRead:
    try:
        wf = await create_workflow(db, data)
        await db.commit()
        return WorkflowRead.model_validate(wf)
    except WorkflowNotFoundError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("", response_model=WorkflowList)
async def list_workflows_endpoint(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    is_active: bool | None = Query(None),
    search: str | None = Query(None, max_length=255),
    db: AsyncSession = Depends(get_db),
) -> WorkflowList:
    items, total = await list_workflows(
        db, offset=offset, limit=limit, is_active=is_active, search=search
    )
    return WorkflowList(
        items=[WorkflowRead.model_validate(w) for w in items],
        total=total, offset=offset, limit=limit,
    )


@router.get("/{wf_id}", response_model=WorkflowRead)
async def get_workflow_endpoint(
    wf_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> WorkflowRead:
    try:
        wf = await get_workflow(db, wf_id)
        return WorkflowRead.model_validate(wf)
    except WorkflowNotFoundError:
        raise HTTPException(status_code=404, detail=f"Workflow {wf_id} not found")


@router.put("/{wf_id}", response_model=WorkflowRead)
async def update_workflow_endpoint(
    wf_id: uuid.UUID,
    data: WorkflowUpdate,
    db: AsyncSession = Depends(get_db),
) -> WorkflowRead:
    try:
        wf = await update_workflow(db, wf_id, data)
        await db.commit()
        return WorkflowRead.model_validate(wf)
    except WorkflowNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{wf_id}", response_model=WorkflowRead)
async def delete_workflow_endpoint(
    wf_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> WorkflowRead:
    try:
        wf = await delete_workflow(db, wf_id)
        await db.commit()
        return WorkflowRead.model_validate(wf)
    except WorkflowNotFoundError:
        raise HTTPException(status_code=404, detail=f"Workflow {wf_id} not found")


@router.get("/{wf_id}/graph", response_model=WorkflowGraphExport)
async def get_workflow_graph_endpoint(
    wf_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> WorkflowGraphExport:
    """Return the node/edge graph for the UI builder."""
    try:
        return await export_graph(db, wf_id)
    except WorkflowNotFoundError:
        raise HTTPException(status_code=404, detail=f"Workflow {wf_id} not found")


@router.post("/{wf_id}/validate", response_model=ValidationResult)
async def validate_workflow_endpoint(
    wf_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ValidationResult:
    """Validate that a workflow is complete and ready for execution."""
    try:
        return await validate_workflow(db, wf_id)
    except WorkflowNotFoundError:
        raise HTTPException(status_code=404, detail=f"Workflow {wf_id} not found")
