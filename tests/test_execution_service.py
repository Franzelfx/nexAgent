"""Tests for the execution tracker service (S6.2)."""

from __future__ import annotations

import uuid

import pytest

from nexagent.services.execution_service import (
    ExecutionNotFoundError,
    complete_execution,
    complete_lane,
    create_execution,
    create_lane,
    delete_execution,
    get_execution,
    list_executions,
    record_step,
    start_execution,
    start_lane,
)


class TestExecutionService:
    async def test_create_execution(self, db_session):
        exc = await create_execution(db_session, None, "Test task")
        assert exc.id is not None
        assert exc.task_input == "Test task"
        assert exc.status == "pending"
        assert exc.workflow_id is None

    async def test_create_execution_with_workflow(self, db_session):
        from nexagent.models.workflow import Workflow
        wf = Workflow(name="test-wf")
        db_session.add(wf)
        await db_session.flush()

        exc = await create_execution(db_session, wf.id, "Run workflow")
        assert exc.workflow_id == wf.id

    async def test_get_execution(self, db_session):
        exc = await create_execution(db_session, None, "Test")
        loaded = await get_execution(db_session, exc.id)
        assert loaded.id == exc.id
        assert loaded.task_input == "Test"

    async def test_get_execution_not_found(self, db_session):
        with pytest.raises(ExecutionNotFoundError):
            await get_execution(db_session, uuid.uuid4())

    async def test_start_execution(self, db_session):
        exc = await create_execution(db_session, None, "Test")
        started = await start_execution(db_session, exc.id)
        assert started.status == "running"
        assert started.started_at is not None

    async def test_list_executions(self, db_session):
        await create_execution(db_session, None, "Task 1")
        await create_execution(db_session, None, "Task 2")
        items, total = await list_executions(db_session)
        assert total >= 2

    async def test_list_executions_filter_status(self, db_session):
        exc = await create_execution(db_session, None, "Task")
        await start_execution(db_session, exc.id)
        items, total = await list_executions(db_session, status="running")
        assert any(e.status == "running" for e in items)

    async def test_delete_execution(self, db_session):
        exc = await create_execution(db_session, None, "To delete")
        await delete_execution(db_session, exc.id)
        with pytest.raises(ExecutionNotFoundError):
            await get_execution(db_session, exc.id)


class TestLaneTracking:
    async def test_create_lane(self, db_session):
        exc = await create_execution(db_session, None, "Test")
        lane = await create_lane(
            db_session, exc.id, 0, "master", None, "Master Orchestrator",
        )
        assert lane.lane_index == 0
        assert lane.actor_type == "master"
        assert lane.status == "pending"

    async def test_start_and_complete_lane(self, db_session):
        exc = await create_execution(db_session, None, "Test")
        lane = await create_lane(db_session, exc.id, 0, "master", None, "Master")
        started = await start_lane(db_session, lane.id)
        assert started.status == "running"
        assert started.started_at is not None

        completed = await complete_lane(db_session, lane.id, "completed")
        assert completed.status == "completed"
        assert completed.finished_at is not None

    async def test_record_step(self, db_session):
        exc = await create_execution(db_session, None, "Test")
        lane = await create_lane(db_session, exc.id, 0, "master", None, "Master")
        step = await record_step(
            db_session, lane.id, 1, "llm_call",
            input_data={"prompt": "test"},
            output_data={"response": "hello"},
            model_used="gpt-4o",
            tokens_prompt=100,
            tokens_completion=50,
            duration_ms=500,
        )
        assert step.step_index == 1
        assert step.step_type == "llm_call"
        assert step.tokens_prompt == 100
        assert step.model_used == "gpt-4o"

    async def test_complete_execution_aggregates_tokens(self, db_session):
        exc = await create_execution(db_session, None, "Test")
        lane = await create_lane(db_session, exc.id, 0, "master", None, "Master")
        await record_step(
            db_session, lane.id, 1, "llm_call",
            tokens_prompt=100, tokens_completion=50,
            model_used="gpt-4o",
        )
        await record_step(
            db_session, lane.id, 2, "llm_call",
            tokens_prompt=200, tokens_completion=100,
            model_used="gpt-4o",
        )

        result = await complete_execution(
            db_session, exc.id, final_output="Done", status="completed",
        )
        assert result.total_tokens == 450  # 100+50+200+100
        assert result.total_cost_usd is not None
        assert result.total_cost_usd > 0
        assert result.final_output == "Done"
        assert result.status == "completed"


class TestMultipleLanes:
    async def test_execution_with_multiple_lanes(self, db_session):
        exc = await create_execution(db_session, None, "Multi-lane test")
        master = await create_lane(db_session, exc.id, 0, "master", None, "Master")
        agent1 = await create_lane(db_session, exc.id, 1, "sub_agent", uuid.uuid4(), "Researcher")
        agent2 = await create_lane(db_session, exc.id, 2, "sub_agent", uuid.uuid4(), "Writer")

        await record_step(db_session, master.id, 1, "delegation")
        await record_step(db_session, agent1.id, 1, "llm_call", tokens_prompt=50, tokens_completion=20)
        await record_step(db_session, agent2.id, 1, "llm_call", tokens_prompt=80, tokens_completion=30)
        # Save id before expiring to avoid lazy-load in async context
        exc_id = exc.id
        db_session.expire(exc)
        loaded = await get_execution(db_session, exc_id)
        assert len(loaded.lanes) == 3
        assert loaded.lanes[0].actor_type == "master"
        assert loaded.lanes[1].actor_name == "Researcher"
        assert loaded.lanes[2].actor_name == "Writer"
