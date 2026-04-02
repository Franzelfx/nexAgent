"""create tool_definitions table

Revision ID: 002
Revises: 001
Create Date: 2026-04-01
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tool_definitions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("tool_type", sa.String(50), nullable=False),
        sa.Column("input_schema", JSONB, nullable=False, server_default="{}"),
        sa.Column("output_schema", JSONB, nullable=True),
        sa.Column("config", JSONB, nullable=True, server_default="{}"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "tool_type IN ('builtin', 'api_call', 'function', 'mcp')",
            name="ck_tool_definitions_tool_type_valid",
        ),
        schema="nexagent",
    )


def downgrade() -> None:
    op.drop_table("tool_definitions", schema="nexagent")
