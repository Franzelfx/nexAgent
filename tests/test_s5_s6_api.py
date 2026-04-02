"""Integration tests for Execution, Timeline, and History API endpoints (S5.6, S6.3, S6.5, S6.6)."""

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


# ---------------------------------------------------------------------------
# Helper: create a valid workflow (orchestrator + sub-agent) via API
# ---------------------------------------------------------------------------


async def _create_workflow(client: AsyncClient) -> dict:
    """Create a minimal workflow with orchestrator and sub-agent so it passes validation."""
    # Create sub-agent
    agent_resp = await client.post("/api/v1/sub-agents", json={
        "name": f"exec_agent_{uuid.uuid4().hex[:8]}",
        "role_description": "Test executor agent",
        "provider": "openai",
        "model_name": "gpt-4o",
    })
    assert agent_resp.status_code == 201
    agent_id = agent_resp.json()["id"]

    # Create orchestrator with sub-agent
    orch_resp = await client.post("/api/v1/orchestrators", json={
        "name": f"exec_orch_{uuid.uuid4().hex[:8]}",
        "provider": "openai",
        "model_name": "gpt-4o",
        "strategy": "parallel",
        "sub_agent_ids": [agent_id],
    })
    assert orch_resp.status_code == 201
    orch_id = orch_resp.json()["id"]

    # Create workflow with orchestrator
    wf_resp = await client.post("/api/v1/workflows", json={
        "name": f"exec_wf_{uuid.uuid4().hex[:8]}",
        "orchestrator_id": orch_id,
    })
    assert wf_resp.status_code == 201
    return wf_resp.json()


# ---------------------------------------------------------------------------
# Execution CRUD tests (S5.6)
# ---------------------------------------------------------------------------


class TestExecutionEndpoints:
    async def test_execute_missing_workflow_returns_404(self, client):
        resp = await client.post("/api/v1/execute", json={
            "workflow_id": str(uuid.uuid4()),
            "task_input": "do something",
        })
        assert resp.status_code == 404

    async def test_list_executions_empty(self, client):
        resp = await client.get("/api/v1/executions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 0
        assert isinstance(data["items"], list)

    async def test_get_execution_not_found(self, client):
        resp = await client.get(f"/api/v1/executions/{uuid.uuid4()}")
        assert resp.status_code == 404

    async def test_cancel_nonexistent_execution(self, client):
        resp = await client.post(f"/api/v1/executions/{uuid.uuid4()}/cancel")
        assert resp.status_code == 404

    async def test_delete_nonexistent_execution(self, client):
        resp = await client.delete(f"/api/v1/executions/{uuid.uuid4()}")
        assert resp.status_code == 404

    async def test_timeline_nonexistent_execution(self, client):
        resp = await client.get(f"/api/v1/executions/{uuid.uuid4()}/timeline")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Execution service-level creation and timeline (via DB directly)
# ---------------------------------------------------------------------------


class TestExecutionServiceViaDB:
    """Tests using the service layer directly to create executions with lanes/steps,
    then querying them through the API."""

    async def test_execution_detail_with_lanes(self, client):
        """Create execution via service, then GET it via API."""
        from nexagent import database

        async with database.async_session() as db:
            from nexagent.services.execution_service import (
                create_execution,
                create_lane,
                record_step,
                complete_execution,
                start_execution,
            )

            exc = await create_execution(db, None, "Test lane retrieval")
            await start_execution(db, exc.id)

            master = await create_lane(db, exc.id, 0, "master", None, "Master")
            await record_step(db, master.id, 1, "llm_call",
                              model_used="gpt-4o", tokens_prompt=100, tokens_completion=50)
            await record_step(db, master.id, 2, "synthesis",
                              output_data={"result": "synthesized"})

            agent_lane = await create_lane(db, exc.id, 1, "sub_agent", uuid.uuid4(), "Agent1")
            await record_step(db, agent_lane.id, 1, "llm_call",
                              model_used="gpt-4o", tokens_prompt=80, tokens_completion=40)

            await complete_execution(db, exc.id, final_output="Done", status="completed")
            await db.commit()
            exc_id = exc.id

        # GET the execution via API
        resp = await client.get(f"/api/v1/executions/{exc_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["final_output"] == "Done"
        assert data["total_tokens"] == 270  # 100+50+80+40
        assert len(data["lanes"]) == 2
        assert data["lanes"][0]["actor_type"] == "master"
        assert len(data["lanes"][0]["steps"]) == 2
        assert len(data["lanes"][1]["steps"]) == 1

    async def test_timeline_endpoint(self, client):
        """Create execution with lanes/steps, then GET timeline."""
        from nexagent import database

        async with database.async_session() as db:
            from nexagent.services.execution_service import (
                create_execution,
                create_lane,
                record_step,
                complete_execution,
                start_execution,
            )

            exc = await create_execution(db, None, "Timeline test")
            await start_execution(db, exc.id)

            master = await create_lane(db, exc.id, 0, "master", None, "Master")
            await record_step(db, master.id, 1, "llm_call", duration_ms=100)
            await record_step(db, master.id, 2, "delegation", duration_ms=10)

            sub = await create_lane(db, exc.id, 1, "sub_agent", uuid.uuid4(), "Worker")
            await record_step(db, sub.id, 1, "llm_call", duration_ms=200)
            await record_step(db, sub.id, 2, "tool_call", duration_ms=50,
                              input_data={"tool": "calculator"}, output_data={"result": "42"})

            await complete_execution(db, exc.id, final_output="42", status="completed")
            await db.commit()
            exc_id = exc.id

        # GET timeline without data
        resp = await client.get(f"/api/v1/executions/{exc_id}/timeline")
        assert resp.status_code == 200
        data = resp.json()
        assert data["execution_id"] == str(exc_id)
        assert data["status"] == "completed"
        assert len(data["lanes"]) == 2
        # Steps are ordered
        assert data["lanes"][0]["steps"][0]["step_index"] == 1
        assert data["lanes"][0]["steps"][1]["step_index"] == 2
        # Input/output data excluded by default
        assert data["lanes"][1]["steps"][1]["input_data"] is None

        # GET timeline with include_data
        resp2 = await client.get(f"/api/v1/executions/{exc_id}/timeline?include_data=true")
        data2 = resp2.json()
        assert data2["lanes"][1]["steps"][1]["input_data"] == {"tool": "calculator"}
        assert data2["lanes"][1]["steps"][1]["output_data"] == {"result": "42"}

    async def test_list_executions_with_filters(self, client):
        from nexagent import database

        async with database.async_session() as db:
            from nexagent.services.execution_service import create_execution, start_execution

            e1 = await create_execution(db, None, "Task A")
            await start_execution(db, e1.id)
            e2 = await create_execution(db, None, "Task B")
            await db.commit()

        # Filter by status
        resp = await client.get("/api/v1/executions?status=running")
        assert resp.status_code == 200
        data = resp.json()
        assert all(i["status"] == "running" for i in data["items"])

    async def test_cancel_execution(self, client):
        from nexagent import database

        async with database.async_session() as db:
            from nexagent.services.execution_service import create_execution

            exc = await create_execution(db, None, "Cancel me")
            await db.commit()
            exc_id = exc.id

        resp = await client.post(f"/api/v1/executions/{exc_id}/cancel")
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

        # Verify it's cancelled
        resp2 = await client.get(f"/api/v1/executions/{exc_id}")
        assert resp2.json()["status"] == "cancelled"

    async def test_cancel_completed_returns_409(self, client):
        from nexagent import database

        async with database.async_session() as db:
            from nexagent.services.execution_service import (
                create_execution, complete_execution,
            )

            exc = await create_execution(db, None, "Completed task")
            await complete_execution(db, exc.id, final_output="done", status="completed")
            await db.commit()
            exc_id = exc.id

        resp = await client.post(f"/api/v1/executions/{exc_id}/cancel")
        assert resp.status_code == 409

    async def test_delete_execution_cascade(self, client):
        from nexagent import database

        async with database.async_session() as db:
            from nexagent.services.execution_service import (
                create_execution, create_lane, record_step,
            )

            exc = await create_execution(db, None, "Delete cascade test")
            lane = await create_lane(db, exc.id, 0, "master", None, "Master")
            await record_step(db, lane.id, 1, "llm_call")
            await db.commit()
            exc_id = exc.id

        resp = await client.delete(f"/api/v1/executions/{exc_id}")
        assert resp.status_code == 204

        # Verify it's gone
        resp2 = await client.get(f"/api/v1/executions/{exc_id}")
        assert resp2.status_code == 404

    async def test_execution_cost_tracking(self, client):
        """Verify cost is aggregated from step token counts."""
        from nexagent import database

        async with database.async_session() as db:
            from nexagent.services.execution_service import (
                create_execution, create_lane, record_step, complete_execution,
            )

            exc = await create_execution(db, None, "Cost tracking test")
            lane = await create_lane(db, exc.id, 0, "master", None, "Master")
            await record_step(db, lane.id, 1, "llm_call",
                              model_used="gpt-4o", tokens_prompt=1000, tokens_completion=500)
            await complete_execution(db, exc.id, final_output="done", status="completed")
            await db.commit()
            exc_id = exc.id

        resp = await client.get(f"/api/v1/executions/{exc_id}")
        data = resp.json()
        assert data["total_tokens"] == 1500
        assert data["total_cost_usd"] is not None
        assert data["total_cost_usd"] > 0
