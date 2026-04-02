"""Orchestrator CRUD service."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from nexagent.models.orchestrator import Orchestrator, orchestrator_sub_agents
from nexagent.models.sub_agent import SubAgent
from nexagent.schemas.orchestrators import OrchestratorCreate, OrchestratorUpdate
from nexagent.services.crypto import encrypt_api_key


class OrchestratorServiceError(Exception):
    pass


class OrchestratorNotFoundError(OrchestratorServiceError):
    pass


async def _load_sub_agents(db: AsyncSession, ids: list[uuid.UUID]) -> list[SubAgent]:
    """Load and validate sub-agent references."""
    if not ids:
        return []
    result = await db.execute(
        select(SubAgent).where(SubAgent.id.in_(ids), SubAgent.is_active.is_(True))
    )
    agents = list(result.scalars().all())
    found = {a.id for a in agents}
    missing = set(ids) - found
    if missing:
        raise OrchestratorNotFoundError(
            f"Sub-agents not found or inactive: {', '.join(str(m) for m in missing)}"
        )
    return agents


async def create_orchestrator(db: AsyncSession, data: OrchestratorCreate) -> Orchestrator:
    """Create a new orchestrator with optional sub-agent bindings."""
    orch = Orchestrator(
        name=data.name,
        description=data.description,
        system_prompt=data.system_prompt,
        provider=data.provider,
        model_name=data.model_name,
        temperature=data.temperature,
        max_tokens=data.max_tokens,
        strategy=data.strategy.value,
        max_iterations=data.max_iterations,
        config=data.config,
    )
    if data.api_key:
        orch.api_key_encrypted = encrypt_api_key(data.api_key)

    if data.sub_agent_ids:
        orch.sub_agents = await _load_sub_agents(db, data.sub_agent_ids)

    db.add(orch)
    await db.flush()
    await db.refresh(orch)
    return orch


async def get_orchestrator(db: AsyncSession, orch_id: uuid.UUID) -> Orchestrator:
    """Get a single orchestrator by ID (with sub-agents and their tools eager-loaded)."""
    result = await db.execute(
        select(Orchestrator)
        .options(selectinload(Orchestrator.sub_agents).selectinload(SubAgent.tools))
        .where(Orchestrator.id == orch_id)
    )
    orch = result.scalar_one_or_none()
    if orch is None:
        raise OrchestratorNotFoundError(f"Orchestrator {orch_id} not found")
    return orch


async def list_orchestrators(
    db: AsyncSession,
    *,
    offset: int = 0,
    limit: int = 50,
    is_active: bool | None = None,
    search: str | None = None,
) -> tuple[list[Orchestrator], int]:
    """List orchestrators with optional filters."""
    query = select(Orchestrator).options(
        selectinload(Orchestrator.sub_agents).selectinload(SubAgent.tools)
    )
    count_query = select(func.count()).select_from(Orchestrator)

    if is_active is not None:
        query = query.where(Orchestrator.is_active == is_active)
        count_query = count_query.where(Orchestrator.is_active == is_active)
    if search:
        pattern = f"%{search}%"
        query = query.where(Orchestrator.name.ilike(pattern))
        count_query = count_query.where(Orchestrator.name.ilike(pattern))

    total = (await db.execute(count_query)).scalar_one()
    query = query.order_by(Orchestrator.created_at.desc()).offset(offset).limit(limit)
    items = list((await db.execute(query)).scalars().unique().all())
    return items, total


async def update_orchestrator(db: AsyncSession, orch_id: uuid.UUID, data: OrchestratorUpdate) -> Orchestrator:
    """Update an existing orchestrator."""
    orch = await get_orchestrator(db, orch_id)
    update_data = data.model_dump(exclude_unset=True)

    api_key = update_data.pop("api_key", None)
    if api_key:
        orch.api_key_encrypted = encrypt_api_key(api_key)

    if "strategy" in update_data and update_data["strategy"] is not None:
        update_data["strategy"] = update_data["strategy"].value

    for field, value in update_data.items():
        setattr(orch, field, value)

    await db.flush()
    await db.refresh(orch)
    return orch


async def delete_orchestrator(db: AsyncSession, orch_id: uuid.UUID) -> Orchestrator:
    """Soft-delete an orchestrator."""
    orch = await get_orchestrator(db, orch_id)
    orch.is_active = False
    await db.flush()
    await db.refresh(orch)
    return orch


async def bind_sub_agents(
    db: AsyncSession, orch_id: uuid.UUID, sub_agent_ids: list[uuid.UUID]
) -> Orchestrator:
    """Replace all sub-agent bindings for an orchestrator."""
    orch = await get_orchestrator(db, orch_id)
    orch.sub_agents = await _load_sub_agents(db, sub_agent_ids) if sub_agent_ids else []
    await db.flush()
    await db.refresh(orch)
    return orch


async def add_sub_agent(db: AsyncSession, orch_id: uuid.UUID, sub_agent_id: uuid.UUID) -> Orchestrator:
    """Add a single sub-agent to an orchestrator."""
    orch = await get_orchestrator(db, orch_id)
    agents = await _load_sub_agents(db, [sub_agent_id])
    existing_ids = {a.id for a in orch.sub_agents}
    if sub_agent_id not in existing_ids:
        orch.sub_agents = list(orch.sub_agents) + agents
        await db.flush()
        await db.refresh(orch)
    return orch


async def remove_sub_agent(db: AsyncSession, orch_id: uuid.UUID, sub_agent_id: uuid.UUID) -> Orchestrator:
    """Remove a single sub-agent from an orchestrator."""
    orch = await get_orchestrator(db, orch_id)
    orch.sub_agents = [a for a in orch.sub_agents if a.id != sub_agent_id]
    await db.flush()
    await db.refresh(orch)
    return orch
