"""Orchestrator ORM model."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, Column, ForeignKey, Integer, String, Table, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from nexagent.models.base import Base, TimestampMixin

# Many-to-many join table: orchestrators ↔ sub_agents
orchestrator_sub_agents = Table(
    "orchestrator_sub_agents",
    Base.metadata,
    Column(
        "orchestrator_id",
        UUID(as_uuid=True),
        ForeignKey("orchestrators.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "sub_agent_id",
        UUID(as_uuid=True),
        ForeignKey("sub_agents.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("priority", Integer, default=0),
)


class Orchestrator(Base, TimestampMixin):
    """Master orchestrator that delegates work to sub-agents."""

    __tablename__ = "orchestrators"
    __table_args__ = (
        CheckConstraint(
            "strategy IN ('parallel', 'sequential', 'adaptive')",
            name="strategy_valid",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    temperature: Mapped[float] = mapped_column(default=0.0)
    max_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    strategy: Mapped[str] = mapped_column(String(50), server_default="parallel")
    max_iterations: Mapped[int] = mapped_column(Integer, server_default="5")
    config: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True, server_default="{}")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    # Relationships
    sub_agents = relationship("SubAgent", secondary=orchestrator_sub_agents, lazy="selectin")
