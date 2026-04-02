"""Integration tests for Sub-Agent, Orchestrator, and Workflow REST API endpoints."""

from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import text

from nexagent.api import app
from nexagent.config import settings
from nexagent.models.base import SCHEMA, Base


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
async def client():
    from nexagent import database
    from nexagent.services import builtin_sync

    test_engine = create_async_engine(settings.database_url, echo=False)
    test_sf = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    async with test_engine.begin() as conn:
        await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}"))
        await conn.run_sync(Base.metadata.create_all)

    orig_engine = database.engine
    orig_session = database.async_session
    orig_bs_session = builtin_sync.async_session

    database.engine = test_engine
    database.async_session = test_sf
    builtin_sync.async_session = test_sf

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    database.engine = orig_engine
    database.async_session = orig_session
    builtin_sync.async_session = orig_bs_session
    await test_engine.dispose()


@pytest.fixture
def agent_payload() -> dict:
    return {
        "name": f"api_agent_{uuid.uuid4().hex[:8]}",
        "role_description": "A test agent",
        "provider": "openai",
        "model_name": "gpt-4o",
        "temperature": 0.5,
    }


@pytest.fixture
def orch_payload() -> dict:
    return {
        "name": f"api_orch_{uuid.uuid4().hex[:8]}",
        "description": "A test orchestrator",
        "provider": "openai",
        "model_name": "gpt-4o",
        "strategy": "parallel",
    }


@pytest.fixture
def tool_payload() -> dict:
    return {
        "name": f"api_tool_{uuid.uuid4().hex[:8]}",
        "display_name": "API Test Tool",
        "description": "A tool for testing",
        "tool_type": "api_call",
        "input_schema": {"type": "object"},
    }


# --- Sub-Agent API tests ---


async def test_create_sub_agent(client, agent_payload):
    resp = await client.post("/api/v1/sub-agents", json=agent_payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == agent_payload["name"]
    assert data["provider"] == "openai"
    assert "api_key_encrypted" not in data
    assert "api_key" not in data


async def test_list_sub_agents(client, agent_payload):
    await client.post("/api/v1/sub-agents", json=agent_payload)
    resp = await client.get("/api/v1/sub-agents")
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


async def test_get_sub_agent(client, agent_payload):
    create_resp = await client.post("/api/v1/sub-agents", json=agent_payload)
    agent_id = create_resp.json()["id"]
    resp = await client.get(f"/api/v1/sub-agents/{agent_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == agent_id


async def test_update_sub_agent(client, agent_payload):
    create_resp = await client.post("/api/v1/sub-agents", json=agent_payload)
    agent_id = create_resp.json()["id"]
    resp = await client.put(f"/api/v1/sub-agents/{agent_id}", json={"name": "Updated"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated"


async def test_delete_sub_agent(client, agent_payload):
    create_resp = await client.post("/api/v1/sub-agents", json=agent_payload)
    agent_id = create_resp.json()["id"]
    resp = await client.delete(f"/api/v1/sub-agents/{agent_id}")
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


async def test_sub_agent_tool_binding(client, agent_payload, tool_payload):
    tool_resp = await client.post("/api/v1/tools", json=tool_payload)
    tool_id = tool_resp.json()["id"]
    agent_resp = await client.post("/api/v1/sub-agents", json=agent_payload)
    agent_id = agent_resp.json()["id"]

    # Bind tool
    resp = await client.post(f"/api/v1/sub-agents/{agent_id}/tools/{tool_id}")
    assert resp.status_code == 200
    assert len(resp.json()["tools"]) == 1

    # Remove tool
    resp = await client.delete(f"/api/v1/sub-agents/{agent_id}/tools/{tool_id}")
    assert resp.status_code == 200
    assert len(resp.json()["tools"]) == 0


async def test_sub_agent_not_found(client):
    resp = await client.get(f"/api/v1/sub-agents/{uuid.uuid4()}")
    assert resp.status_code == 404


# --- Orchestrator API tests ---


async def test_create_orchestrator(client, orch_payload):
    resp = await client.post("/api/v1/orchestrators", json=orch_payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["strategy"] == "parallel"


async def test_get_orchestrator(client, orch_payload):
    create_resp = await client.post("/api/v1/orchestrators", json=orch_payload)
    orch_id = create_resp.json()["id"]
    resp = await client.get(f"/api/v1/orchestrators/{orch_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == orch_id


async def test_list_orchestrators(client, orch_payload):
    await client.post("/api/v1/orchestrators", json=orch_payload)
    resp = await client.get("/api/v1/orchestrators")
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


async def test_update_orchestrator(client, orch_payload):
    create_resp = await client.post("/api/v1/orchestrators", json=orch_payload)
    orch_id = create_resp.json()["id"]
    resp = await client.put(f"/api/v1/orchestrators/{orch_id}", json={"strategy": "sequential"})
    assert resp.status_code == 200
    assert resp.json()["strategy"] == "sequential"


async def test_delete_orchestrator(client, orch_payload):
    create_resp = await client.post("/api/v1/orchestrators", json=orch_payload)
    orch_id = create_resp.json()["id"]
    resp = await client.delete(f"/api/v1/orchestrators/{orch_id}")
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


async def test_orchestrator_sub_agent_binding(client, orch_payload, agent_payload):
    agent_resp = await client.post("/api/v1/sub-agents", json=agent_payload)
    agent_id = agent_resp.json()["id"]
    orch_resp = await client.post("/api/v1/orchestrators", json=orch_payload)
    orch_id = orch_resp.json()["id"]

    # Add sub-agent
    resp = await client.post(f"/api/v1/orchestrators/{orch_id}/sub-agents/{agent_id}")
    assert resp.status_code == 200
    assert len(resp.json()["sub_agents"]) == 1

    # Remove sub-agent
    resp = await client.delete(f"/api/v1/orchestrators/{orch_id}/sub-agents/{agent_id}")
    assert resp.status_code == 200
    assert len(resp.json()["sub_agents"]) == 0


async def test_capability_map(client, orch_payload, agent_payload):
    agent_resp = await client.post("/api/v1/sub-agents", json=agent_payload)
    agent_id = agent_resp.json()["id"]
    orch_payload["sub_agent_ids"] = [agent_id]
    orch_resp = await client.post("/api/v1/orchestrators", json=orch_payload)
    orch_id = orch_resp.json()["id"]

    resp = await client.get(f"/api/v1/orchestrators/{orch_id}/capability-map")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["entries"]) == 1
    assert data["summary"] != ""


async def test_orchestrator_not_found(client):
    resp = await client.get(f"/api/v1/orchestrators/{uuid.uuid4()}")
    assert resp.status_code == 404


# --- Workflow API tests ---


async def test_create_workflow(client, orch_payload):
    orch_resp = await client.post("/api/v1/orchestrators", json=orch_payload)
    orch_id = orch_resp.json()["id"]
    resp = await client.post("/api/v1/workflows", json={"name": "Test WF", "orchestrator_id": orch_id})
    assert resp.status_code == 201
    assert resp.json()["orchestrator_id"] == orch_id


async def test_get_workflow(client):
    resp = await client.post("/api/v1/workflows", json={"name": "Get WF"})
    wf_id = resp.json()["id"]
    resp = await client.get(f"/api/v1/workflows/{wf_id}")
    assert resp.status_code == 200


async def test_list_workflows(client):
    await client.post("/api/v1/workflows", json={"name": "List WF"})
    resp = await client.get("/api/v1/workflows")
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


async def test_update_workflow(client):
    create_resp = await client.post("/api/v1/workflows", json={"name": "Update WF"})
    wf_id = create_resp.json()["id"]
    resp = await client.put(f"/api/v1/workflows/{wf_id}", json={"name": "Updated"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated"


async def test_delete_workflow(client):
    create_resp = await client.post("/api/v1/workflows", json={"name": "Delete WF"})
    wf_id = create_resp.json()["id"]
    resp = await client.delete(f"/api/v1/workflows/{wf_id}")
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


async def test_validate_workflow_invalid(client):
    create_resp = await client.post("/api/v1/workflows", json={"name": "Invalid WF"})
    wf_id = create_resp.json()["id"]
    resp = await client.post(f"/api/v1/workflows/{wf_id}/validate")
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is False
    assert len(data["errors"]) > 0


async def test_validate_workflow_valid(client, orch_payload, agent_payload):
    agent_resp = await client.post("/api/v1/sub-agents", json=agent_payload)
    agent_id = agent_resp.json()["id"]
    orch_payload["sub_agent_ids"] = [agent_id]
    orch_resp = await client.post("/api/v1/orchestrators", json=orch_payload)
    orch_id = orch_resp.json()["id"]
    wf_resp = await client.post("/api/v1/workflows", json={"name": "Valid WF", "orchestrator_id": orch_id})
    wf_id = wf_resp.json()["id"]
    resp = await client.post(f"/api/v1/workflows/{wf_id}/validate")
    assert resp.status_code == 200
    assert resp.json()["valid"] is True


async def test_workflow_graph_export(client, orch_payload, agent_payload, tool_payload):
    # Create tool
    tool_resp = await client.post("/api/v1/tools", json=tool_payload)
    tool_id = tool_resp.json()["id"]
    # Create agent with tool
    agent_payload["tool_ids"] = [tool_id]
    agent_resp = await client.post("/api/v1/sub-agents", json=agent_payload)
    agent_id = agent_resp.json()["id"]
    # Create orchestrator with agent
    orch_payload["sub_agent_ids"] = [agent_id]
    orch_resp = await client.post("/api/v1/orchestrators", json=orch_payload)
    orch_id = orch_resp.json()["id"]
    # Create workflow
    wf_resp = await client.post("/api/v1/workflows", json={"name": "Graph WF", "orchestrator_id": orch_id})
    wf_id = wf_resp.json()["id"]

    resp = await client.get(f"/api/v1/workflows/{wf_id}/graph")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["nodes"]) == 3
    assert len(data["edges"]) == 2


async def test_workflow_not_found(client):
    resp = await client.get(f"/api/v1/workflows/{uuid.uuid4()}")
    assert resp.status_code == 404
