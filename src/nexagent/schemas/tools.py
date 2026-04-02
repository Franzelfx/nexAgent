"""Pydantic schemas for Tool Definition API."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ToolType(str, enum.Enum):
    builtin = "builtin"
    api_call = "api_call"
    function = "function"
    mcp = "mcp"


class ToolCreate(BaseModel):
    """Request body for creating a tool definition."""

    name: str = Field(..., min_length=1, max_length=255, examples=["web_search"])
    display_name: str = Field(..., min_length=1, max_length=255, examples=["Web Search"])
    description: str = Field(..., min_length=1, examples=["Search the web for information"])
    tool_type: ToolType = Field(..., examples=[ToolType.api_call])
    input_schema: dict[str, Any] = Field(
        default_factory=dict,
        examples=[{"type": "object", "properties": {"query": {"type": "string"}}}],
    )
    output_schema: dict[str, Any] | None = None
    config: dict[str, Any] | None = None


class ToolUpdate(BaseModel):
    """Request body for updating a tool definition. All fields optional."""

    name: str | None = Field(None, min_length=1, max_length=255)
    display_name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, min_length=1)
    tool_type: ToolType | None = None
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    config: dict[str, Any] | None = None
    is_active: bool | None = None


class ToolRead(BaseModel):
    """Response schema for a single tool definition."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    display_name: str
    description: str
    tool_type: ToolType
    input_schema: dict[str, Any]
    output_schema: dict[str, Any] | None
    config: dict[str, Any] | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ToolList(BaseModel):
    """Paginated list of tool definitions."""

    items: list[ToolRead]
    total: int
    offset: int
    limit: int
