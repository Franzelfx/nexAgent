"""Pydantic schemas for Orchestrator API."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from nexagent.schemas.sub_agents import SubAgentRead


class Strategy(str, enum.Enum):
    parallel = "parallel"
    sequential = "sequential"
    adaptive = "adaptive"


class OrchestratorCreate(BaseModel):
    """Request body for creating an orchestrator."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    system_prompt: str | None = None
    provider: str = Field(..., min_length=1, max_length=50)
    model_name: str = Field(..., min_length=1, max_length=255)
    api_key: str | None = Field(None, description="Plaintext API key — encrypted at rest, never returned")
    temperature: float = Field(0.0, ge=0.0, le=2.0)
    max_tokens: int | None = Field(None, gt=0)
    strategy: Strategy = Strategy.parallel
    max_iterations: int = Field(5, ge=1, le=100)
    config: dict[str, Any] | None = None
    sub_agent_ids: list[uuid.UUID] = Field(default_factory=list)


class OrchestratorUpdate(BaseModel):
    """Request body for updating an orchestrator. All fields optional."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    system_prompt: str | None = None
    provider: str | None = Field(None, min_length=1, max_length=50)
    model_name: str | None = Field(None, min_length=1, max_length=255)
    api_key: str | None = Field(None, description="Plaintext API key — encrypted at rest")
    temperature: float | None = Field(None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(None, gt=0)
    strategy: Strategy | None = None
    max_iterations: int | None = Field(None, ge=1, le=100)
    config: dict[str, Any] | None = None
    is_active: bool | None = None


class CapabilityMapEntry(BaseModel):
    """A single entry in the capability map."""

    sub_agent_id: uuid.UUID
    sub_agent_name: str
    role_description: str
    provider: str
    model_name: str
    tools: list[str]


class CapabilityMap(BaseModel):
    """Auto-generated capability description for an orchestrator."""

    orchestrator_id: uuid.UUID
    orchestrator_name: str
    strategy: str
    entries: list[CapabilityMapEntry]
    summary: str = ""


class OrchestratorRead(BaseModel):
    """Response schema for a single orchestrator."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    system_prompt: str | None
    provider: str
    model_name: str
    temperature: float
    max_tokens: int | None
    strategy: str
    max_iterations: int
    config: dict[str, Any] | None
    is_active: bool
    sub_agents: list[SubAgentRead] = []
    created_at: datetime
    updated_at: datetime


class OrchestratorList(BaseModel):
    """Paginated list of orchestrators."""

    items: list[OrchestratorRead]
    total: int
    offset: int
    limit: int
