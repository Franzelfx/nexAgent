"""Orchestration state — flows through the multi-agent execution graph."""

from __future__ import annotations

import operator
import uuid
from typing import Annotated, Any

from pydantic import BaseModel, Field


class DelegationTask(BaseModel):
    """A sub-task assigned to a specific sub-agent."""

    sub_agent_id: uuid.UUID
    sub_agent_name: str = ""
    sub_task: str
    status: str = "pending"  # pending | running | completed | failed
    result: str | None = None
    error: str | None = None
    tokens_used: int = 0
    duration_ms: int = 0
    tool_calls_log: list[dict[str, Any]] = Field(default_factory=list)


class OrchestrationState(BaseModel):
    """State that flows through the master orchestration graph.

    Attributes:
        execution_id: DB execution row ID for persistence.
        workflow_id: The workflow being executed.
        task_input: The user's original instruction.
        plan: The master's current delegation plan (natural language).
        delegations: Sub-tasks assigned to sub-agents (append-only via reducer).
        lane_results: Collected outputs per lane (append-only via reducer).
        final_output: Synthesized answer from all sub-agent results.
        iteration_count: How many plan→delegate→collect cycles so far.
        max_iterations: Hard limit from orchestrator config.
        status: Overall execution status.
        capability_summary: Natural-language capability map for the master prompt.
        error: Error message if execution failed.
    """

    execution_id: uuid.UUID | None = None
    workflow_id: uuid.UUID | None = None
    task_input: str = ""
    plan: str = ""
    delegations: Annotated[list[DelegationTask], operator.add] = Field(default_factory=list)
    lane_results: Annotated[list[dict[str, Any]], operator.add] = Field(default_factory=list)
    final_output: str = ""
    iteration_count: int = 0
    max_iterations: int = 5
    status: str = "pending"
    capability_summary: str = ""
    error: str = ""
