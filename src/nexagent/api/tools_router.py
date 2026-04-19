"""Tool definition REST API endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from nexagent.database import get_db
from nexagent.schemas.tools import ToolCreate, ToolList, ToolRead, ToolUpdate
from nexagent.services.tool_service import (
    ToolConflictError,
    ToolNotFoundError,
    create_tool,
    delete_tool,
    get_tool,
    list_tools,
    update_tool,
)

router = APIRouter(prefix="/api/v1/tools", tags=["tools"])


@router.post("", response_model=ToolRead, status_code=201)
async def create_tool_endpoint(
    data: ToolCreate,
    db: AsyncSession = Depends(get_db),
) -> ToolRead:
    """Create a new tool definition."""
    try:
        tool = await create_tool(db, data)
        await db.commit()
        return ToolRead.model_validate(tool)
    except ToolConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("", response_model=ToolList)
async def list_tools_endpoint(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    tool_type: str | None = Query(None),
    is_active: bool | None = Query(None),
    search: str | None = Query(None, max_length=255),
    db: AsyncSession = Depends(get_db),
) -> ToolList:
    """List tool definitions with optional filters."""
    items, total = await list_tools(
        db, offset=offset, limit=limit, tool_type=tool_type, is_active=is_active, search=search
    )
    return ToolList(
        items=[ToolRead.model_validate(t) for t in items],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/{tool_id}", response_model=ToolRead)
async def get_tool_endpoint(
    tool_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ToolRead:
    """Get a single tool definition."""
    try:
        tool = await get_tool(db, tool_id)
        return ToolRead.model_validate(tool)
    except ToolNotFoundError:
        raise HTTPException(status_code=404, detail=f"Tool {tool_id} not found")


@router.put("/{tool_id}", response_model=ToolRead)
async def update_tool_endpoint(
    tool_id: uuid.UUID,
    data: ToolUpdate,
    db: AsyncSession = Depends(get_db),
) -> ToolRead:
    """Update a tool definition."""
    try:
        tool = await update_tool(db, tool_id, data)
        await db.commit()
        return ToolRead.model_validate(tool)
    except ToolNotFoundError:
        raise HTTPException(status_code=404, detail=f"Tool {tool_id} not found")
    except ToolConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.delete("/{tool_id}", response_model=ToolRead)
async def delete_tool_endpoint(
    tool_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ToolRead:
    """Soft-delete a tool definition (sets is_active = false)."""
    try:
        tool = await delete_tool(db, tool_id)
        await db.commit()
        return ToolRead.model_validate(tool)
    except ToolNotFoundError:
        raise HTTPException(status_code=404, detail=f"Tool {tool_id} not found")
    except ToolConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))


# --- Probe endpoint ---


import time
from pydantic import BaseModel, Field
from typing import Any


class ToolProbeRequest(BaseModel):
    input: dict[str, Any] = Field(default_factory=dict, description="Tool call arguments matching input_schema.")


class ToolProbeResponse(BaseModel):
    output: str
    duration_ms: int = 0
    error: str | None = None


@router.post("/{tool_id}/probe", response_model=ToolProbeResponse)
async def probe_tool_endpoint(
    tool_id: uuid.UUID,
    data: ToolProbeRequest,
    db: AsyncSession = Depends(get_db),
) -> ToolProbeResponse:
    """Invoke a tool once with typed arguments, bypassing any agent loop."""
    from nexagent.engine.tool_executor import resolve_tools

    try:
        tool_def = await get_tool(db, tool_id)
    except ToolNotFoundError:
        raise HTTPException(status_code=404, detail=f"Tool {tool_id} not found")

    start = time.monotonic()
    try:
        [callable_tool] = resolve_tools([tool_def])
        result = await callable_tool.ainvoke(data.input)
        elapsed = int((time.monotonic() - start) * 1000)
        return ToolProbeResponse(output=str(result), duration_ms=elapsed)
    except Exception as e:
        elapsed = int((time.monotonic() - start) * 1000)
        return ToolProbeResponse(output="", duration_ms=elapsed, error=str(e))
