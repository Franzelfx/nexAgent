"""Tests for the lane manager (S5.5)."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from nexagent.engine.lane_manager import execute_delegations
from nexagent.state.orchestration import DelegationTask


def _make_agent(name: str = "test-agent") -> SimpleNamespace:
    """Create a minimal SubAgent-like object for testing (avoids SQLAlchemy instrumentation)."""
    return SimpleNamespace(
        id=uuid.uuid4(),
        name=name,
        role_description="Test role",
        system_prompt=None,
        provider="openai",
        model_name="gpt-4o",
        api_key_encrypted=None,
        temperature=0.0,
        max_tokens=None,
        config={},
        is_active=True,
        tools=[],
    )


class TestLaneManager:
    async def test_empty_delegations(self):
        result = await execute_delegations([], {})
        assert result == []

    @patch("nexagent.engine.lane_manager.run_sub_agent")
    async def test_parallel_execution(self, mock_run):
        mock_run.return_value = {
            "output": "done",
            "tool_calls_log": [],
            "tokens_used": 100,
            "duration_ms": 500,
        }
        agent = _make_agent()
        d = DelegationTask(
            sub_agent_id=agent.id,
            sub_agent_name=agent.name,
            sub_task="do something",
        )
        result = await execute_delegations(
            [d], {str(agent.id): agent}, strategy="parallel",
        )
        assert len(result) == 1
        assert result[0].status == "completed"
        assert result[0].result == "done"
        assert result[0].tokens_used == 100

    @patch("nexagent.engine.lane_manager.run_sub_agent")
    async def test_sequential_execution(self, mock_run):
        mock_run.return_value = {
            "output": "sequential done",
            "tool_calls_log": [],
            "tokens_used": 50,
            "duration_ms": 200,
        }
        agent = _make_agent()
        d = DelegationTask(
            sub_agent_id=agent.id,
            sub_agent_name=agent.name,
            sub_task="sequential task",
        )
        result = await execute_delegations(
            [d], {str(agent.id): agent}, strategy="sequential",
        )
        assert result[0].status == "completed"
        assert result[0].result == "sequential done"

    async def test_missing_agent(self):
        d = DelegationTask(
            sub_agent_id=uuid.uuid4(),
            sub_agent_name="ghost",
            sub_task="fail",
        )
        result = await execute_delegations([d], {}, strategy="parallel")
        assert result[0].status == "failed"
        assert "not found" in result[0].error

    @patch("nexagent.engine.lane_manager.run_sub_agent")
    async def test_partial_failure(self, mock_run):
        """One agent fails, the other succeeds."""
        agent1 = _make_agent("agent1")
        agent2 = _make_agent("agent2")

        call_count = 0

        async def side_effect(agent, task):
            nonlocal call_count
            call_count += 1
            if agent.name == "agent1":
                return {"output": "ok", "tool_calls_log": [], "tokens_used": 10, "duration_ms": 100}
            raise RuntimeError("agent2 crashed")

        mock_run.side_effect = side_effect

        d1 = DelegationTask(sub_agent_id=agent1.id, sub_agent_name="agent1", sub_task="t1")
        d2 = DelegationTask(sub_agent_id=agent2.id, sub_agent_name="agent2", sub_task="t2")

        result = await execute_delegations(
            [d1, d2],
            {str(agent1.id): agent1, str(agent2.id): agent2},
            strategy="parallel",
        )
        statuses = {r.sub_agent_name: r.status for r in result}
        assert statuses["agent1"] == "completed"
        assert statuses["agent2"] == "failed"

    @patch("nexagent.engine.lane_manager.run_sub_agent")
    async def test_multiple_parallel(self, mock_run):
        mock_run.return_value = {
            "output": "result",
            "tool_calls_log": [{"tool": "calc", "args": {}}],
            "tokens_used": 75,
            "duration_ms": 300,
        }
        agents = [_make_agent(f"a{i}") for i in range(3)]
        delegations = [
            DelegationTask(sub_agent_id=a.id, sub_agent_name=a.name, sub_task=f"task{i}")
            for i, a in enumerate(agents)
        ]
        agents_map = {str(a.id): a for a in agents}

        result = await execute_delegations(delegations, agents_map, strategy="parallel")
        assert len(result) == 3
        assert all(r.status == "completed" for r in result)
        assert all(len(r.tool_calls_log) == 1 for r in result)
