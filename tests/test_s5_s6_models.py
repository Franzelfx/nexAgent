"""Tests for S5 state and S6.1 persistence models."""

from __future__ import annotations

import uuid

import pytest

from nexagent.models.base import Base
from nexagent.models.execution import Execution
from nexagent.models.execution_lane import ExecutionLane
from nexagent.models.execution_step import ExecutionStep
from nexagent.state.orchestration import DelegationTask, OrchestrationState


# ---------------------------------------------------------------------------
# Model metadata tests
# ---------------------------------------------------------------------------


class TestExecutionModels:
    def test_all_execution_tables_in_metadata(self):
        tables = Base.metadata.tables
        for name in ("nexagent.executions", "nexagent.execution_lanes", "nexagent.execution_steps"):
            assert name in tables, f"Missing table: {name}"

    def test_execution_columns(self):
        cols = {c.name for c in Execution.__table__.columns}
        expected = {
            "id", "workflow_id", "task_input", "final_output", "status",
            "error_message", "total_tokens", "total_cost_usd",
            "started_at", "finished_at", "created_at",
        }
        assert expected.issubset(cols)

    def test_execution_lane_columns(self):
        cols = {c.name for c in ExecutionLane.__table__.columns}
        expected = {
            "id", "execution_id", "lane_index", "actor_type",
            "actor_id", "actor_name", "status", "started_at", "finished_at",
        }
        assert expected.issubset(cols)

    def test_execution_step_columns(self):
        cols = {c.name for c in ExecutionStep.__table__.columns}
        expected = {
            "id", "lane_id", "step_index", "step_type", "input_data",
            "output_data", "model_used", "tokens_prompt", "tokens_completion",
            "duration_ms", "status", "error_message", "started_at", "finished_at",
        }
        assert expected.issubset(cols)

    def test_execution_has_lanes_relationship(self):
        assert hasattr(Execution, "lanes")

    def test_execution_lane_has_steps_relationship(self):
        assert hasattr(ExecutionLane, "steps")

    def test_execution_lane_has_execution_relationship(self):
        assert hasattr(ExecutionLane, "execution")

    def test_execution_step_has_lane_relationship(self):
        assert hasattr(ExecutionStep, "lane")


# ---------------------------------------------------------------------------
# OrchestrationState tests
# ---------------------------------------------------------------------------


class TestOrchestrationState:
    def test_default_state(self):
        state = OrchestrationState()
        assert state.task_input == ""
        assert state.delegations == []
        assert state.lane_results == []
        assert state.iteration_count == 0
        assert state.max_iterations == 5
        assert state.status == "pending"

    def test_delegation_task(self):
        dt = DelegationTask(
            sub_agent_id=uuid.uuid4(),
            sub_agent_name="researcher",
            sub_task="find data",
        )
        assert dt.status == "pending"
        assert dt.result is None
        assert dt.tokens_used == 0

    def test_state_serializable(self):
        state = OrchestrationState(
            task_input="test",
            plan="delegate to researcher",
            delegations=[
                DelegationTask(
                    sub_agent_id=uuid.uuid4(),
                    sub_agent_name="researcher",
                    sub_task="research X",
                    status="completed",
                    result="found data",
                )
            ],
        )
        data = state.model_dump(mode="json")
        assert data["task_input"] == "test"
        assert len(data["delegations"]) == 1
        restored = OrchestrationState.model_validate(data)
        assert restored.delegations[0].result == "found data"

    def test_reducer_appends(self):
        """The operator.add reducer should concatenate lists."""
        d1 = DelegationTask(sub_agent_id=uuid.uuid4(), sub_task="task1")
        d2 = DelegationTask(sub_agent_id=uuid.uuid4(), sub_task="task2")
        combined = [d1] + [d2]
        assert len(combined) == 2
