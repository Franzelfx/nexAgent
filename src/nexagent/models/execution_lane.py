"""ExecutionLane ORM model."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from nexagent.models.base import Base


class ExecutionLane(Base):
    """One lane per actor in a single execution — maps to guitar-view rows."""

    __tablename__ = "execution_lanes"
    __table_args__ = (
        UniqueConstraint("execution_id", "lane_index", name="uq_execution_lanes_exec_lane"),
        CheckConstraint(
            "actor_type IN ('master', 'sub_agent')",
            name="lane_actor_type_valid",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    execution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("executions.id", ondelete="CASCADE"),
        nullable=False,
    )
    lane_index: Mapped[int] = mapped_column(Integer, nullable=False)
    actor_type: Mapped[str] = mapped_column(String(30), nullable=False)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    actor_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="pending")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    execution = relationship("Execution", back_populates="lanes")
    steps = relationship(
        "ExecutionStep",
        back_populates="lane",
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="ExecutionStep.step_index",
    )
