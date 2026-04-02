"""Tool definition CRUD service."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from nexagent.models.tool_definition import ToolDefinition
from nexagent.schemas.tools import ToolCreate, ToolUpdate


class ToolServiceError(Exception):
    """Base error for tool service operations."""


class ToolNotFoundError(ToolServiceError):
    """Raised when a tool is not found."""


class ToolConflictError(ToolServiceError):
    """Raised on duplicate name or disallowed operation."""


async def create_tool(db: AsyncSession, data: ToolCreate) -> ToolDefinition:
    """Create a new tool definition."""
    tool = ToolDefinition(
        name=data.name,
        display_name=data.display_name,
        description=data.description,
        tool_type=data.tool_type.value,
        input_schema=data.input_schema,
        output_schema=data.output_schema,
        config=data.config,
    )
    db.add(tool)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise ToolConflictError(f"Tool with name '{data.name}' already exists")
    await db.refresh(tool)
    return tool


async def get_tool(db: AsyncSession, tool_id: uuid.UUID) -> ToolDefinition:
    """Get a single tool definition by ID."""
    result = await db.execute(select(ToolDefinition).where(ToolDefinition.id == tool_id))
    tool = result.scalar_one_or_none()
    if tool is None:
        raise ToolNotFoundError(f"Tool {tool_id} not found")
    return tool


async def list_tools(
    db: AsyncSession,
    *,
    offset: int = 0,
    limit: int = 50,
    tool_type: str | None = None,
    is_active: bool | None = None,
    search: str | None = None,
) -> tuple[list[ToolDefinition], int]:
    """List tool definitions with optional filters. Returns (items, total)."""
    query = select(ToolDefinition)
    count_query = select(func.count()).select_from(ToolDefinition)

    if tool_type is not None:
        query = query.where(ToolDefinition.tool_type == tool_type)
        count_query = count_query.where(ToolDefinition.tool_type == tool_type)
    if is_active is not None:
        query = query.where(ToolDefinition.is_active == is_active)
        count_query = count_query.where(ToolDefinition.is_active == is_active)
    if search:
        pattern = f"%{search}%"
        query = query.where(ToolDefinition.name.ilike(pattern) | ToolDefinition.display_name.ilike(pattern))
        count_query = count_query.where(
            ToolDefinition.name.ilike(pattern) | ToolDefinition.display_name.ilike(pattern)
        )

    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    query = query.order_by(ToolDefinition.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    items = list(result.scalars().all())

    return items, total


async def update_tool(db: AsyncSession, tool_id: uuid.UUID, data: ToolUpdate) -> ToolDefinition:
    """Update an existing tool definition."""
    tool = await get_tool(db, tool_id)
    update_data = data.model_dump(exclude_unset=True)

    if "tool_type" in update_data and update_data["tool_type"] is not None:
        update_data["tool_type"] = update_data["tool_type"].value

    for field, value in update_data.items():
        setattr(tool, field, value)

    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise ToolConflictError(f"Tool with name '{data.name}' already exists")
    await db.refresh(tool)
    return tool


async def delete_tool(db: AsyncSession, tool_id: uuid.UUID) -> ToolDefinition:
    """Soft-delete a tool (set is_active = False). Built-in tools cannot be deleted."""
    tool = await get_tool(db, tool_id)
    if tool.tool_type == "builtin":
        raise ToolConflictError("Built-in tools cannot be deleted")
    tool.is_active = False
    await db.flush()
    await db.refresh(tool)
    return tool
