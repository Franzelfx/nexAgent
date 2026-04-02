"""Tests for the tool service layer (requires running PostgreSQL)."""

from __future__ import annotations

import uuid

import pytest

from nexagent.models.tool_definition import ToolDefinition
from nexagent.schemas.tools import ToolCreate, ToolType, ToolUpdate
from nexagent.services.tool_service import (
    ToolConflictError,
    ToolNotFoundError,
    create_tool,
    delete_tool,
    get_tool,
    list_tools,
    update_tool,
)


@pytest.fixture
def sample_tool_data() -> ToolCreate:
    return ToolCreate(
        name=f"test_tool_{uuid.uuid4().hex[:8]}",
        display_name="Test Tool",
        description="A test tool",
        tool_type=ToolType.api_call,
        input_schema={"type": "object", "properties": {"q": {"type": "string"}}},
    )


@pytest.mark.asyncio
async def test_create_tool(db_session, sample_tool_data):
    tool = await create_tool(db_session, sample_tool_data)
    assert tool.id is not None
    assert tool.name == sample_tool_data.name
    assert tool.tool_type == "api_call"
    assert tool.is_active is True


@pytest.mark.asyncio
async def test_create_duplicate_name_raises(db_session, sample_tool_data):
    await create_tool(db_session, sample_tool_data)
    with pytest.raises(ToolConflictError, match="already exists"):
        await create_tool(db_session, sample_tool_data)


@pytest.mark.asyncio
async def test_get_tool(db_session, sample_tool_data):
    created = await create_tool(db_session, sample_tool_data)
    found = await get_tool(db_session, created.id)
    assert found.id == created.id
    assert found.name == sample_tool_data.name


@pytest.mark.asyncio
async def test_get_tool_not_found(db_session):
    with pytest.raises(ToolNotFoundError):
        await get_tool(db_session, uuid.uuid4())


@pytest.mark.asyncio
async def test_list_tools(db_session, sample_tool_data):
    await create_tool(db_session, sample_tool_data)
    items, total = await list_tools(db_session)
    assert total >= 1
    assert any(t.name == sample_tool_data.name for t in items)


@pytest.mark.asyncio
async def test_list_tools_filter_by_type(db_session, sample_tool_data):
    await create_tool(db_session, sample_tool_data)
    items, total = await list_tools(db_session, tool_type="api_call")
    assert all(t.tool_type == "api_call" for t in items)


@pytest.mark.asyncio
async def test_list_tools_search(db_session, sample_tool_data):
    await create_tool(db_session, sample_tool_data)
    items, total = await list_tools(db_session, search=sample_tool_data.name[:10])
    assert total >= 1


@pytest.mark.asyncio
async def test_update_tool(db_session, sample_tool_data):
    created = await create_tool(db_session, sample_tool_data)
    updated = await update_tool(db_session, created.id, ToolUpdate(display_name="Updated Name"))
    assert updated.display_name == "Updated Name"
    assert updated.name == sample_tool_data.name


@pytest.mark.asyncio
async def test_delete_tool_soft(db_session, sample_tool_data):
    created = await create_tool(db_session, sample_tool_data)
    deleted = await delete_tool(db_session, created.id)
    assert deleted.is_active is False


@pytest.mark.asyncio
async def test_delete_builtin_tool_raises(db_session):
    builtin_data = ToolCreate(
        name=f"builtin_{uuid.uuid4().hex[:8]}",
        display_name="Builtin Tool",
        description="A builtin tool",
        tool_type=ToolType.builtin,
        input_schema={},
    )
    tool = await create_tool(db_session, builtin_data)
    with pytest.raises(ToolConflictError, match="Built-in tools cannot be deleted"):
        await delete_tool(db_session, tool.id)
