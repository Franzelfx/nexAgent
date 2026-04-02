"""sub_agents, orchestrators, workflows tables

Revision ID: 003
Revises: 002
Create Date: 2026-04-01
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None

SCHEMA = "nexagent"


def upgrade() -> None:
    # --- sub_agents ---
    op.create_table(
        "sub_agents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("role_description", sa.Text, nullable=False),
        sa.Column("system_prompt", sa.Text, nullable=True),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("model_name", sa.String(255), nullable=False),
        sa.Column("api_key_encrypted", sa.Text, nullable=True),
        sa.Column("temperature", sa.Double(), server_default="0.0"),
        sa.Column("max_tokens", sa.Integer, nullable=True),
        sa.Column("config", postgresql.JSONB(), server_default="{}"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema=SCHEMA,
    )

    # --- sub_agent_tools (join) ---
    op.create_table(
        "sub_agent_tools",
        sa.Column(
            "sub_agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{SCHEMA}.sub_agents.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "tool_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{SCHEMA}.tool_definitions.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("priority", sa.Integer, server_default="0"),
        schema=SCHEMA,
    )

    # --- orchestrators ---
    op.create_table(
        "orchestrators",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("system_prompt", sa.Text, nullable=True),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("model_name", sa.String(255), nullable=False),
        sa.Column("api_key_encrypted", sa.Text, nullable=True),
        sa.Column("temperature", sa.Double(), server_default="0.0"),
        sa.Column("max_tokens", sa.Integer, nullable=True),
        sa.Column(
            "strategy",
            sa.String(50),
            server_default="parallel",
        ),
        sa.Column("max_iterations", sa.Integer, server_default="5"),
        sa.Column("config", postgresql.JSONB(), server_default="{}"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("strategy IN ('parallel', 'sequential', 'adaptive')", name="strategy_valid"),
        schema=SCHEMA,
    )

    # --- orchestrator_sub_agents (join) ---
    op.create_table(
        "orchestrator_sub_agents",
        sa.Column(
            "orchestrator_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{SCHEMA}.orchestrators.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "sub_agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{SCHEMA}.sub_agents.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("priority", sa.Integer, server_default="0"),
        schema=SCHEMA,
    )

    # --- workflows ---
    op.create_table(
        "workflows",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "orchestrator_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{SCHEMA}.orchestrators.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("graph_layout", postgresql.JSONB(), server_default="{}"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("workflows", schema=SCHEMA)
    op.drop_table("orchestrator_sub_agents", schema=SCHEMA)
    op.drop_table("orchestrators", schema=SCHEMA)
    op.drop_table("sub_agent_tools", schema=SCHEMA)
    op.drop_table("sub_agents", schema=SCHEMA)
