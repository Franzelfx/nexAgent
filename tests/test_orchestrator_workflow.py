"""Tests for orchestrator and workflow service layers (requires PostgreSQL)."""

from __future__ import annotations

import uuid

import pytest

from nexagent.config import settings
from nexagent.schemas.orchestrators import OrchestratorCreate, OrchestratorUpdate, Strategy
from nexagent.schemas.sub_agents import Provider, SubAgentCreate
from nexagent.schemas.workflows import WorkflowCreate, WorkflowUpdate
from nexagent.schemas.tools import ToolCreate, ToolType
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
from nexagent.services.sub_agent_service import create_sub_agent
from nexagent.services.tool_service import create_tool
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
from nexagent.engine.capability_map import build_capability_map


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
def orch_data() -> OrchestratorCreate:
    return OrchestratorCreate(
        name=f"test_orch_{uuid.uuid4().hex[:8]}",
        description="A test orchestrator",
        provider="openai",
        model_name="gpt-4o",
        strategy=Strategy.parallel,
    )


@pytest.fixture
async def sample_agent(db_session):
    return await create_sub_agent(
        db_session,
        SubAgentCreate(
            name=f"agent_{uuid.uuid4().hex[:8]}",
            role_description="Test agent for research",
            provider=Provider.openai,
            model_name="gpt-4o",
        ),
    )


@pytest.fixture
async def sample_tool(db_session):
    return await create_tool(
        db_session,
        ToolCreate(
            name=f"tool_{uuid.uuid4().hex[:8]}",
            display_name="Test Tool",
            description="A test tool",
            tool_type=ToolType.api_call,
            input_schema={"type": "object"},
        ),
    )


# --- Orchestrator tests ---


async def test_create_orchestrator(db_session, orch_data):
    orch = await create_orchestrator(db_session, orch_data)
    assert orch.id is not None
    assert orch.strategy == "parallel"


async def test_create_orchestrator_with_agents(db_session, orch_data, sample_agent):
    orch_data.sub_agent_ids = [sample_agent.id]
    orch = await create_orchestrator(db_session, orch_data)
    assert len(orch.sub_agents) == 1


async def test_get_orchestrator(db_session, orch_data):
    created = await create_orchestrator(db_session, orch_data)
    found = await get_orchestrator(db_session, created.id)
    assert found.id == created.id


async def test_get_orchestrator_not_found(db_session):
    with pytest.raises(OrchestratorNotFoundError):
        await get_orchestrator(db_session, uuid.uuid4())


async def test_list_orchestrators(db_session, orch_data):
    await create_orchestrator(db_session, orch_data)
    items, total = await list_orchestrators(db_session)
    assert total >= 1


async def test_update_orchestrator(db_session, orch_data):
    created = await create_orchestrator(db_session, orch_data)
    updated = await update_orchestrator(
        db_session, created.id, OrchestratorUpdate(strategy=Strategy.sequential)
    )
    assert updated.strategy == "sequential"


async def test_delete_orchestrator(db_session, orch_data):
    created = await create_orchestrator(db_session, orch_data)
    deleted = await delete_orchestrator(db_session, created.id)
    assert deleted.is_active is False


async def test_bind_sub_agents(db_session, orch_data, sample_agent):
    orch = await create_orchestrator(db_session, orch_data)
    orch = await bind_sub_agents(db_session, orch.id, [sample_agent.id])
    assert len(orch.sub_agents) == 1
    orch = await bind_sub_agents(db_session, orch.id, [])
    assert len(orch.sub_agents) == 0


async def test_add_remove_sub_agent(db_session, orch_data, sample_agent):
    orch = await create_orchestrator(db_session, orch_data)
    orch = await add_sub_agent(db_session, orch.id, sample_agent.id)
    assert len(orch.sub_agents) == 1
    orch = await remove_sub_agent(db_session, orch.id, sample_agent.id)
    assert len(orch.sub_agents) == 0


# --- Capability map tests ---


async def test_capability_map_empty(db_session, orch_data):
    orch = await create_orchestrator(db_session, orch_data)
    cap = await build_capability_map(db_session, orch.id)
    assert cap.orchestrator_id == orch.id
    assert len(cap.entries) == 0
    assert "no sub-agents" in cap.summary


async def test_capability_map_with_agents(db_session, orch_data, sample_agent, sample_tool):
    from nexagent.services.sub_agent_service import bind_tools

    await bind_tools(db_session, sample_agent.id, [sample_tool.id])
    orch_data.sub_agent_ids = [sample_agent.id]
    orch = await create_orchestrator(db_session, orch_data)
    cap = await build_capability_map(db_session, orch.id)
    assert len(cap.entries) == 1
    assert sample_tool.name in cap.entries[0].tools


# --- Workflow tests ---


async def test_create_workflow(db_session, orch_data):
    orch = await create_orchestrator(db_session, orch_data)
    wf = await create_workflow(db_session, WorkflowCreate(name="Test WF", orchestrator_id=orch.id))
    assert wf.id is not None
    assert wf.orchestrator_id == orch.id


async def test_create_workflow_no_orchestrator(db_session):
    wf = await create_workflow(db_session, WorkflowCreate(name="Empty WF"))
    assert wf.orchestrator_id is None


async def test_create_workflow_invalid_orchestrator(db_session):
    with pytest.raises(WorkflowNotFoundError):
        await create_workflow(db_session, WorkflowCreate(name="Bad WF", orchestrator_id=uuid.uuid4()))


async def test_get_workflow(db_session):
    wf = await create_workflow(db_session, WorkflowCreate(name="Get WF"))
    found = await get_workflow(db_session, wf.id)
    assert found.id == wf.id


async def test_get_workflow_not_found(db_session):
    with pytest.raises(WorkflowNotFoundError):
        await get_workflow(db_session, uuid.uuid4())


async def test_list_workflows(db_session):
    await create_workflow(db_session, WorkflowCreate(name="List WF"))
    items, total = await list_workflows(db_session)
    assert total >= 1


async def test_update_workflow(db_session):
    wf = await create_workflow(db_session, WorkflowCreate(name="Update WF"))
    updated = await update_workflow(db_session, wf.id, WorkflowUpdate(name="Updated"))
    assert updated.name == "Updated"


async def test_delete_workflow(db_session):
    wf = await create_workflow(db_session, WorkflowCreate(name="Delete WF"))
    deleted = await delete_workflow(db_session, wf.id)
    assert deleted.is_active is False


# --- Validation tests ---


async def test_validate_workflow_no_orchestrator(db_session):
    wf = await create_workflow(db_session, WorkflowCreate(name="No Orch WF"))
    result = await validate_workflow(db_session, wf.id)
    assert result.valid is False
    assert any("no orchestrator" in e for e in result.errors)


async def test_validate_workflow_no_agents(db_session, orch_data):
    orch = await create_orchestrator(db_session, orch_data)
    wf = await create_workflow(db_session, WorkflowCreate(name="No Agents WF", orchestrator_id=orch.id))
    result = await validate_workflow(db_session, wf.id)
    assert result.valid is False
    assert any("no sub-agents" in e for e in result.errors)


async def test_validate_workflow_valid(db_session, orch_data, sample_agent):
    orch_data.sub_agent_ids = [sample_agent.id]
    orch = await create_orchestrator(db_session, orch_data)
    wf = await create_workflow(db_session, WorkflowCreate(name="Valid WF", orchestrator_id=orch.id))
    result = await validate_workflow(db_session, wf.id)
    assert result.valid is True
    assert len(result.errors) == 0


# --- Graph export tests ---


async def test_export_graph_empty(db_session):
    wf = await create_workflow(db_session, WorkflowCreate(name="Graph WF"))
    graph = await export_graph(db_session, wf.id)
    assert graph.workflow_id == wf.id
    assert len(graph.nodes) == 0
    assert len(graph.edges) == 0


async def test_export_graph_with_tree(db_session, orch_data, sample_agent, sample_tool):
    from nexagent.services.sub_agent_service import bind_tools

    await bind_tools(db_session, sample_agent.id, [sample_tool.id])
    orch_data.sub_agent_ids = [sample_agent.id]
    orch = await create_orchestrator(db_session, orch_data)
    wf = await create_workflow(db_session, WorkflowCreate(name="Full Graph WF", orchestrator_id=orch.id))
    graph = await export_graph(db_session, wf.id)
    # Should have: 1 orchestrator + 1 agent + 1 tool = 3 nodes
    assert len(graph.nodes) == 3
    # Should have: orch->agent + agent->tool = 2 edges
    assert len(graph.edges) == 2
    types = {n.type for n in graph.nodes}
    assert types == {"orchestrator", "sub_agent", "tool"}
