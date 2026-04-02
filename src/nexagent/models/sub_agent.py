"""SubAgent ORM model."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Table, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from nexagent.models.base import Base, TimestampMixin

# Many-to-many join table: sub_agents ↔ tool_definitions
sub_agent_tools = Table(
    "sub_agent_tools",
    Base.metadata,
    Column("sub_agent_id", UUID(as_uuid=True), ForeignKey("sub_agents.id", ondelete="CASCADE"), primary_key=True),
    Column("tool_id", UUID(as_uuid=True), ForeignKey("tool_definitions.id", ondelete="CASCADE"), primary_key=True),
    Column("priority", Integer, default=0),
)


class SubAgent(Base, TimestampMixin):
    """An LLM-backed worker agent with a specific role and bound tools."""

    __tablename__ = "sub_agents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role_description: Mapped[str] = mapped_column(Text, nullable=False)
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    temperature: Mapped[float] = mapped_column(default=0.0)
    max_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    config: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True, server_default="{}")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    # Relationships
    tools = relationship("ToolDefinition", secondary=sub_agent_tools, lazy="selectin")
