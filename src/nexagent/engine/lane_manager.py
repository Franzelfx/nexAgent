"""Lane manager — coordinates parallel/sequential sub-agent executions."""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from nexagent.engine.sub_agent_runner import run_sub_agent
from nexagent.models.sub_agent import SubAgent
from nexagent.state.orchestration import DelegationTask

logger = logging.getLogger(__name__)


async def _run_one(
    agent: SubAgent,
    delegation: DelegationTask,
    execution_id: uuid.UUID | None = None,
) -> DelegationTask:
    """Execute a single delegation and return the updated task."""
    delegation.status = "running"
    try:
        result = await run_sub_agent(
            agent, delegation.sub_task, execution_id=execution_id,
        )
        delegation.status = "completed" if "error" not in result else "failed"
        delegation.result = result["output"]
        delegation.tokens_used = result.get("tokens_used", 0)
        delegation.duration_ms = result.get("duration_ms", 0)
        delegation.tool_calls_log = result.get("tool_calls_log", [])
        if "error" in result:
            delegation.error = result["error"]
    except Exception as e:
        logger.error("Sub-agent '%s' crashed: %s", agent.name, e)
        delegation.status = "failed"
        delegation.error = str(e)
    return delegation


async def execute_delegations(
    delegations: list[DelegationTask],
    agents_by_id: dict[str, SubAgent],
    strategy: str = "parallel",
    *,
    execution_id: uuid.UUID | None = None,
) -> list[DelegationTask]:
    """Run sub-agent delegations according to the chosen strategy.

    Args:
        delegations: List of DelegationTask with sub_agent_id and sub_task.
        agents_by_id: Map of str(uuid) → SubAgent ORM instance.
        strategy: "parallel", "sequential", or "adaptive" (treated as parallel).

    Returns:
        The same delegation list with statuses and results filled in.
    """
    if not delegations:
        return delegations

    if strategy == "sequential":
        for d in delegations:
            agent = agents_by_id.get(str(d.sub_agent_id))
            if agent is None:
                d.status = "failed"
                d.error = f"Sub-agent {d.sub_agent_id} not found"
                continue
            await _run_one(agent, d, execution_id=execution_id)
    else:
        # parallel or adaptive — run all concurrently
        tasks = []
        for d in delegations:
            agent = agents_by_id.get(str(d.sub_agent_id))
            if agent is None:
                d.status = "failed"
                d.error = f"Sub-agent {d.sub_agent_id} not found"
                continue
            tasks.append(_run_one(agent, d, execution_id=execution_id))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    return delegations
