"""executions.emit_buffer (Epic 7 — orchestrator pipeline output)

Revision ID: 005
Revises: 004
Create Date: 2026-04-19
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None

SCHEMA = "nexagent"


def upgrade() -> None:
    op.add_column(
        "executions",
        sa.Column("emit_buffer", postgresql.JSONB(), nullable=True),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_column("executions", "emit_buffer", schema=SCHEMA)
