"""Sub-agent CRUD service."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from nexagent.models.sub_agent import SubAgent, sub_agent_tools
from nexagent.models.tool_definition import ToolDefinition
from nexagent.schemas.sub_agents import SubAgentCreate, SubAgentUpdate
from nexagent.services.crypto import encrypt_api_key


class SubAgentServiceError(Exception):
    pass


class SubAgentNotFoundError(SubAgentServiceError):
    pass


class SubAgentConflictError(SubAgentServiceError):
    pass


async def _load_tools(db: AsyncSession, tool_ids: list[uuid.UUID]) -> list[ToolDefinition]:
    """Load and validate tool references. Raises if any are missing or inactive."""
    if not tool_ids:
        return []
    result = await db.execute(
        select(ToolDefinition).where(ToolDefinition.id.in_(tool_ids), ToolDefinition.is_active.is_(True))
    )
    tools = list(result.scalars().all())
    found_ids = {t.id for t in tools}
    missing = set(tool_ids) - found_ids
    if missing:
        raise SubAgentNotFoundError(f"Tools not found or inactive: {', '.join(str(m) for m in missing)}")
    return tools


async def create_sub_agent(db: AsyncSession, data: SubAgentCreate) -> SubAgent:
    """Create a new sub-agent with optional tool bindings."""
    agent = SubAgent(
        name=data.name,
        role_description=data.role_description,
        system_prompt=data.system_prompt,
        provider=data.provider.value,
        model_name=data.model_name,
        temperature=data.temperature,
        max_tokens=data.max_tokens,
        config=data.config,
    )
    if data.api_key:
        agent.api_key_encrypted = encrypt_api_key(data.api_key)

    if data.tool_ids:
        agent.tools = await _load_tools(db, data.tool_ids)

    db.add(agent)
    await db.flush()
    await db.refresh(agent)
    return agent


async def get_sub_agent(db: AsyncSession, agent_id: uuid.UUID) -> SubAgent:
    """Get a single sub-agent by ID (with tools eager-loaded)."""
    result = await db.execute(
        select(SubAgent).options(selectinload(SubAgent.tools)).where(SubAgent.id == agent_id)
    )
    agent = result.scalar_one_or_none()
    if agent is None:
        raise SubAgentNotFoundError(f"Sub-agent {agent_id} not found")
    return agent


async def list_sub_agents(
    db: AsyncSession,
    *,
    offset: int = 0,
    limit: int = 50,
    provider: str | None = None,
    is_active: bool | None = None,
    search: str | None = None,
) -> tuple[list[SubAgent], int]:
    """List sub-agents with optional filters."""
    query = select(SubAgent).options(selectinload(SubAgent.tools))
    count_query = select(func.count()).select_from(SubAgent)

    if provider is not None:
        query = query.where(SubAgent.provider == provider)
        count_query = count_query.where(SubAgent.provider == provider)
    if is_active is not None:
        query = query.where(SubAgent.is_active == is_active)
        count_query = count_query.where(SubAgent.is_active == is_active)
    if search:
        pattern = f"%{search}%"
        query = query.where(SubAgent.name.ilike(pattern) | SubAgent.role_description.ilike(pattern))
        count_query = count_query.where(SubAgent.name.ilike(pattern) | SubAgent.role_description.ilike(pattern))

    total = (await db.execute(count_query)).scalar_one()
    query = query.order_by(SubAgent.created_at.desc()).offset(offset).limit(limit)
    items = list((await db.execute(query)).scalars().unique().all())
    return items, total


async def update_sub_agent(db: AsyncSession, agent_id: uuid.UUID, data: SubAgentUpdate) -> SubAgent:
    """Update an existing sub-agent."""
    agent = await get_sub_agent(db, agent_id)
    update_data = data.model_dump(exclude_unset=True)

    api_key = update_data.pop("api_key", None)
    if api_key:
        agent.api_key_encrypted = encrypt_api_key(api_key)

    if "provider" in update_data and update_data["provider"] is not None:
        update_data["provider"] = update_data["provider"].value

    for field, value in update_data.items():
        setattr(agent, field, value)

    await db.flush()
    await db.refresh(agent)
    return agent


async def delete_sub_agent(db: AsyncSession, agent_id: uuid.UUID) -> SubAgent:
    """Soft-delete a sub-agent (set is_active = False)."""
    agent = await get_sub_agent(db, agent_id)
    agent.is_active = False
    await db.flush()
    await db.refresh(agent)
    return agent


async def bind_tools(db: AsyncSession, agent_id: uuid.UUID, tool_ids: list[uuid.UUID]) -> SubAgent:
    """Replace all tool bindings for a sub-agent."""
    agent = await get_sub_agent(db, agent_id)
    agent.tools = await _load_tools(db, tool_ids) if tool_ids else []
    await db.flush()
    await db.refresh(agent)
    return agent


async def add_tool(db: AsyncSession, agent_id: uuid.UUID, tool_id: uuid.UUID) -> SubAgent:
    """Add a single tool to a sub-agent."""
    agent = await get_sub_agent(db, agent_id)
    tools = await _load_tools(db, [tool_id])
    existing_ids = {t.id for t in agent.tools}
    if tool_id not in existing_ids:
        agent.tools = list(agent.tools) + tools
        await db.flush()
        await db.refresh(agent)
    return agent


async def remove_tool(db: AsyncSession, agent_id: uuid.UUID, tool_id: uuid.UUID) -> SubAgent:
    """Remove a single tool from a sub-agent."""
    agent = await get_sub_agent(db, agent_id)
    agent.tools = [t for t in agent.tools if t.id != tool_id]
    await db.flush()
    await db.refresh(agent)
    return agent
