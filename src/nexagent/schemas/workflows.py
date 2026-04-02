"""Pydantic schemas for Workflow API."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from nexagent.schemas.orchestrators import OrchestratorRead


class WorkflowCreate(BaseModel):
    """Request body for creating a workflow."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    orchestrator_id: uuid.UUID | None = None
    graph_layout: dict[str, Any] | None = None


class WorkflowUpdate(BaseModel):
    """Request body for updating a workflow. All fields optional."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    orchestrator_id: uuid.UUID | None = None
    graph_layout: dict[str, Any] | None = None
    is_active: bool | None = None


class WorkflowRead(BaseModel):
    """Response schema for a single workflow."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    orchestrator_id: uuid.UUID | None
    graph_layout: dict[str, Any] | None
    is_active: bool
    orchestrator: OrchestratorRead | None = None
    created_at: datetime
    updated_at: datetime


class WorkflowList(BaseModel):
    """Paginated list of workflows."""

    items: list[WorkflowRead]
    total: int
    offset: int
    limit: int


class ValidationResult(BaseModel):
    """Result of workflow validation."""

    valid: bool
    errors: list[str] = Field(default_factory=list)


class WorkflowGraphNode(BaseModel):
    """A node in the workflow graph export."""

    id: str
    type: str
    label: str
    position: dict[str, Any] | None = None


class WorkflowGraphEdge(BaseModel):
    """An edge in the workflow graph export."""

    source: str
    target: str
    label: str | None = None


class WorkflowGraphExport(BaseModel):
    """Full node/edge representation of a workflow for the UI builder."""

    workflow_id: uuid.UUID
    nodes: list[WorkflowGraphNode]
    edges: list[WorkflowGraphEdge]
