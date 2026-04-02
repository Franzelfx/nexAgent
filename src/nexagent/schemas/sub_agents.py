"""Pydantic schemas for Sub-Agent API."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from nexagent.schemas.tools import ToolRead


class Provider(str, enum.Enum):
    openai = "openai"
    anthropic = "anthropic"
    litellm = "litellm"
    custom = "custom"


class SubAgentCreate(BaseModel):
    """Request body for creating a sub-agent."""

    name: str = Field(..., min_length=1, max_length=255)
    role_description: str = Field(..., min_length=1)
    system_prompt: str | None = None
    provider: Provider
    model_name: str = Field(..., min_length=1, max_length=255)
    api_key: str | None = Field(None, description="Plaintext API key — encrypted at rest, never returned")
    temperature: float = Field(0.0, ge=0.0, le=2.0)
    max_tokens: int | None = Field(None, gt=0)
    config: dict[str, Any] | None = None
    tool_ids: list[uuid.UUID] = Field(default_factory=list)


class SubAgentUpdate(BaseModel):
    """Request body for updating a sub-agent. All fields optional."""

    name: str | None = Field(None, min_length=1, max_length=255)
    role_description: str | None = Field(None, min_length=1)
    system_prompt: str | None = None
    provider: Provider | None = None
    model_name: str | None = Field(None, min_length=1, max_length=255)
    api_key: str | None = Field(None, description="Plaintext API key — encrypted at rest")
    temperature: float | None = Field(None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(None, gt=0)
    config: dict[str, Any] | None = None
    is_active: bool | None = None


class SubAgentRead(BaseModel):
    """Response schema for a single sub-agent (API key never exposed)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    role_description: str
    system_prompt: str | None
    provider: str
    model_name: str
    temperature: float
    max_tokens: int | None
    config: dict[str, Any] | None
    is_active: bool
    tools: list[ToolRead] = []
    created_at: datetime
    updated_at: datetime


class SubAgentList(BaseModel):
    """Paginated list of sub-agents."""

    items: list[SubAgentRead]
    total: int
    offset: int
    limit: int
