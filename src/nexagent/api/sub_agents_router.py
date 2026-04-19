"""Sub-agent REST API endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from nexagent.database import get_db
from nexagent.schemas.sub_agents import SubAgentCreate, SubAgentList, SubAgentRead, SubAgentUpdate
from nexagent.services.sub_agent_service import (
    SubAgentConflictError,
    SubAgentNotFoundError,
    add_tool,
    bind_tools,
    create_sub_agent,
    delete_sub_agent,
    get_sub_agent,
    list_sub_agents,
    remove_tool,
    update_sub_agent,
)

router = APIRouter(prefix="/api/v1/sub-agents", tags=["sub-agents"])


@router.post("", response_model=SubAgentRead, status_code=201)
async def create_sub_agent_endpoint(
    data: SubAgentCreate,
    db: AsyncSession = Depends(get_db),
) -> SubAgentRead:
    try:
        agent = await create_sub_agent(db, data)
        await db.commit()
        return SubAgentRead.model_validate(agent)
    except SubAgentNotFoundError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("", response_model=SubAgentList)
async def list_sub_agents_endpoint(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    provider: str | None = Query(None),
    is_active: bool | None = Query(None),
    search: str | None = Query(None, max_length=255),
    db: AsyncSession = Depends(get_db),
) -> SubAgentList:
    items, total = await list_sub_agents(
        db, offset=offset, limit=limit, provider=provider, is_active=is_active, search=search
    )
    return SubAgentList(
        items=[SubAgentRead.model_validate(a) for a in items],
        total=total, offset=offset, limit=limit,
    )


@router.get("/{agent_id}", response_model=SubAgentRead)
async def get_sub_agent_endpoint(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> SubAgentRead:
    try:
        agent = await get_sub_agent(db, agent_id)
        return SubAgentRead.model_validate(agent)
    except SubAgentNotFoundError:
        raise HTTPException(status_code=404, detail=f"Sub-agent {agent_id} not found")


@router.put("/{agent_id}", response_model=SubAgentRead)
async def update_sub_agent_endpoint(
    agent_id: uuid.UUID,
    data: SubAgentUpdate,
    db: AsyncSession = Depends(get_db),
) -> SubAgentRead:
    try:
        agent = await update_sub_agent(db, agent_id, data)
        await db.commit()
        return SubAgentRead.model_validate(agent)
    except SubAgentNotFoundError:
        raise HTTPException(status_code=404, detail=f"Sub-agent {agent_id} not found")


@router.delete("/{agent_id}", response_model=SubAgentRead)
async def delete_sub_agent_endpoint(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> SubAgentRead:
    try:
        agent = await delete_sub_agent(db, agent_id)
        await db.commit()
        return SubAgentRead.model_validate(agent)
    except SubAgentNotFoundError:
        raise HTTPException(status_code=404, detail=f"Sub-agent {agent_id} not found")


# --- Tool binding endpoints ---


@router.put("/{agent_id}/tools", response_model=SubAgentRead)
async def bind_tools_endpoint(
    agent_id: uuid.UUID,
    tool_ids: list[uuid.UUID],
    db: AsyncSession = Depends(get_db),
) -> SubAgentRead:
    """Replace all tool bindings for a sub-agent."""
    try:
        agent = await bind_tools(db, agent_id, tool_ids)
        await db.commit()
        return SubAgentRead.model_validate(agent)
    except SubAgentNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{agent_id}/tools/{tool_id}", response_model=SubAgentRead)
async def add_tool_endpoint(
    agent_id: uuid.UUID,
    tool_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> SubAgentRead:
    """Add a single tool to a sub-agent."""
    try:
        agent = await add_tool(db, agent_id, tool_id)
        await db.commit()
        return SubAgentRead.model_validate(agent)
    except SubAgentNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{agent_id}/tools/{tool_id}", response_model=SubAgentRead)
async def remove_tool_endpoint(
    agent_id: uuid.UUID,
    tool_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> SubAgentRead:
    """Remove a single tool from a sub-agent."""
    try:
        agent = await remove_tool(db, agent_id, tool_id)
        await db.commit()
        return SubAgentRead.model_validate(agent)
    except SubAgentNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


# --- Provider validation endpoint ---


@router.post("/{agent_id}/validate")
async def validate_provider_endpoint(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Test that a sub-agent's LLM config is reachable."""
    from nexagent.services.provider_validation import validate_provider

    try:
        return await validate_provider(db, agent_id)
    except SubAgentNotFoundError:
        raise HTTPException(status_code=404, detail=f"Sub-agent {agent_id} not found")


# --- Probe endpoint ---


from pydantic import BaseModel, Field


class SubAgentProbeRequest(BaseModel):
    task_input: str = Field(..., min_length=1, description="User prompt to send to the sub-agent.")


class SubAgentProbeResponse(BaseModel):
    output: str
    tool_calls: list[dict] = Field(default_factory=list)
    tokens_used: int = 0
    duration_ms: int = 0
    error: str | None = None


@router.post("/{agent_id}/probe", response_model=SubAgentProbeResponse)
async def probe_sub_agent_endpoint(
    agent_id: uuid.UUID,
    data: SubAgentProbeRequest,
    db: AsyncSession = Depends(get_db),
) -> SubAgentProbeResponse:
    """Run a sub-agent in isolation against a single prompt (bypasses orchestrator)."""
    from nexagent.engine.sub_agent_runner import run_sub_agent

    try:
        agent = await get_sub_agent(db, agent_id)
    except SubAgentNotFoundError:
        raise HTTPException(status_code=404, detail=f"Sub-agent {agent_id} not found")

    result = await run_sub_agent(agent, data.task_input)
    return SubAgentProbeResponse(
        output=result.get("output", ""),
        tool_calls=result.get("tool_calls_log", []),
        tokens_used=result.get("tokens_used", 0),
        duration_ms=result.get("duration_ms", 0),
        error=result.get("error"),
    )
