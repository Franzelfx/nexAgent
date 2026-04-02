"""Workflow ORM model."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from nexagent.models.base import Base, TimestampMixin


class Workflow(Base, TimestampMixin):
    """A saved configuration snapshot — an orchestrator with its full tree."""

    __tablename__ = "workflows"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    orchestrator_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orchestrators.id", ondelete="SET NULL"),
        nullable=True,
    )
    graph_layout: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True, server_default="{}")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    # Relationships
    orchestrator = relationship("Orchestrator", lazy="selectin")
