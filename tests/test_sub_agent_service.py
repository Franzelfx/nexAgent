"""Tests for the sub-agent service layer (requires PostgreSQL)."""

from __future__ import annotations

import uuid

import pytest

from nexagent.config import settings
from nexagent.models.sub_agent import SubAgent
from nexagent.schemas.sub_agents import Provider, SubAgentCreate, SubAgentUpdate
from nexagent.schemas.tools import ToolCreate, ToolType
from nexagent.services.sub_agent_service import (
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
from nexagent.services.tool_service import create_tool


@pytest.fixture(autouse=True)
def _ensure_encryption_key(monkeypatch):
    from cryptography.fernet import Fernet
    import nexagent.services.crypto as crypto_mod

    if not settings.encryption_key:
        monkeypatch.setattr(settings, "encryption_key", Fernet.generate_key().decode())
    crypto_mod._fernet = None
    yield
    crypto_mod._fernet = None


@pytest.fixture
def agent_data() -> SubAgentCreate:
    return SubAgentCreate(
        name=f"test_agent_{uuid.uuid4().hex[:8]}",
        role_description="A test sub-agent for research",
        provider=Provider.openai,
        model_name="gpt-4o",
        api_key="sk-test-key-123",
        temperature=0.5,
    )


@pytest.fixture
async def sample_tool(db_session):
    tool = await create_tool(
        db_session,
        ToolCreate(
            name=f"tool_{uuid.uuid4().hex[:8]}",
            display_name="Test Tool",
            description="A test tool",
            tool_type=ToolType.api_call,
            input_schema={"type": "object"},
        ),
    )
    return tool


async def test_create_sub_agent(db_session, agent_data):
    agent = await create_sub_agent(db_session, agent_data)
    assert agent.id is not None
    assert agent.name == agent_data.name
    assert agent.provider == "openai"
    assert agent.api_key_encrypted is not None
    assert agent.api_key_encrypted != "sk-test-key-123"


async def test_create_sub_agent_with_tools(db_session, agent_data, sample_tool):
    agent_data.tool_ids = [sample_tool.id]
    agent = await create_sub_agent(db_session, agent_data)
    assert len(agent.tools) == 1
    assert agent.tools[0].id == sample_tool.id


async def test_create_sub_agent_invalid_tool(db_session, agent_data):
    agent_data.tool_ids = [uuid.uuid4()]
    with pytest.raises(SubAgentNotFoundError, match="Tools not found"):
        await create_sub_agent(db_session, agent_data)


async def test_get_sub_agent(db_session, agent_data):
    created = await create_sub_agent(db_session, agent_data)
    found = await get_sub_agent(db_session, created.id)
    assert found.id == created.id


async def test_get_sub_agent_not_found(db_session):
    with pytest.raises(SubAgentNotFoundError):
        await get_sub_agent(db_session, uuid.uuid4())


async def test_list_sub_agents(db_session, agent_data):
    await create_sub_agent(db_session, agent_data)
    items, total = await list_sub_agents(db_session)
    assert total >= 1


async def test_list_sub_agents_filter_provider(db_session, agent_data):
    await create_sub_agent(db_session, agent_data)
    items, total = await list_sub_agents(db_session, provider="openai")
    assert all(a.provider == "openai" for a in items)


async def test_update_sub_agent(db_session, agent_data):
    created = await create_sub_agent(db_session, agent_data)
    updated = await update_sub_agent(db_session, created.id, SubAgentUpdate(name="Updated Agent"))
    assert updated.name == "Updated Agent"


async def test_delete_sub_agent(db_session, agent_data):
    created = await create_sub_agent(db_session, agent_data)
    deleted = await delete_sub_agent(db_session, created.id)
    assert deleted.is_active is False


async def test_bind_tools(db_session, agent_data, sample_tool):
    agent = await create_sub_agent(db_session, agent_data)
    agent = await bind_tools(db_session, agent.id, [sample_tool.id])
    assert len(agent.tools) == 1
    # Clear tools
    agent = await bind_tools(db_session, agent.id, [])
    assert len(agent.tools) == 0


async def test_add_and_remove_tool(db_session, agent_data, sample_tool):
    agent = await create_sub_agent(db_session, agent_data)
    agent = await add_tool(db_session, agent.id, sample_tool.id)
    assert len(agent.tools) == 1
    agent = await remove_tool(db_session, agent.id, sample_tool.id)
    assert len(agent.tools) == 0
