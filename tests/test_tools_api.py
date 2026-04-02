"""Integration tests for Tool REST API endpoints."""

from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from nexagent.api import app
from nexagent.config import settings
from nexagent.models.base import SCHEMA, Base


@pytest.fixture
async def client():
    """Create an ASGI test client with a per-test engine.

    Monkey-patches the module-level engine and session factory in
    ``nexagent.database`` (and its re-exported reference in
    ``nexagent.services.builtin_sync``) so that all connections live
    on the current test's event loop.
    """
    from nexagent import database
    from nexagent.services import builtin_sync
    from sqlalchemy import text

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
def tool_payload() -> dict:
    return {
        "name": f"test_api_tool_{uuid.uuid4().hex[:8]}",
        "display_name": "API Test Tool",
        "description": "A tool for testing the API",
        "tool_type": "api_call",
        "input_schema": {"type": "object", "properties": {"url": {"type": "string"}}},
    }


@pytest.mark.asyncio
async def test_create_tool_endpoint(client, tool_payload):
    resp = await client.post("/api/v1/tools", json=tool_payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == tool_payload["name"]
    assert data["tool_type"] == "api_call"
    assert "id" in data


@pytest.mark.asyncio
async def test_create_duplicate_returns_409(client, tool_payload):
    await client.post("/api/v1/tools", json=tool_payload)
    resp = await client.post("/api/v1/tools", json=tool_payload)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_list_tools_endpoint(client, tool_payload):
    await client.post("/api/v1/tools", json=tool_payload)
    resp = await client.get("/api/v1/tools")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_get_tool_endpoint(client, tool_payload):
    create_resp = await client.post("/api/v1/tools", json=tool_payload)
    tool_id = create_resp.json()["id"]
    resp = await client.get(f"/api/v1/tools/{tool_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == tool_id


@pytest.mark.asyncio
async def test_get_tool_not_found(client):
    resp = await client.get(f"/api/v1/tools/{uuid.uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_tool_endpoint(client, tool_payload):
    create_resp = await client.post("/api/v1/tools", json=tool_payload)
    tool_id = create_resp.json()["id"]
    resp = await client.put(f"/api/v1/tools/{tool_id}", json={"display_name": "Updated"})
    assert resp.status_code == 200
    assert resp.json()["display_name"] == "Updated"


@pytest.mark.asyncio
async def test_delete_tool_endpoint(client, tool_payload):
    create_resp = await client.post("/api/v1/tools", json=tool_payload)
    tool_id = create_resp.json()["id"]
    resp = await client.delete(f"/api/v1/tools/{tool_id}")
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


@pytest.mark.asyncio
async def test_delete_builtin_tool_returns_409(client):
    payload = {
        "name": f"builtin_{uuid.uuid4().hex[:8]}",
        "display_name": "Builtin",
        "description": "A builtin tool",
        "tool_type": "builtin",
        "input_schema": {},
    }
    create_resp = await client.post("/api/v1/tools", json=payload)
    tool_id = create_resp.json()["id"]
    resp = await client.delete(f"/api/v1/tools/{tool_id}")
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_list_tools_with_filters(client, tool_payload):
    await client.post("/api/v1/tools", json=tool_payload)
    resp = await client.get("/api/v1/tools", params={"tool_type": "api_call", "is_active": True})
    assert resp.status_code == 200
    for item in resp.json()["items"]:
        assert item["tool_type"] == "api_call"
        assert item["is_active"] is True


@pytest.mark.asyncio
async def test_list_tools_pagination(client, tool_payload):
    resp = await client.get("/api/v1/tools", params={"limit": 1, "offset": 0})
    assert resp.status_code == 200
    data = resp.json()
    assert data["limit"] == 1
    assert len(data["items"]) <= 1
