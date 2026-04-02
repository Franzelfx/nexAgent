"""executions, execution_lanes, execution_steps tables

Revision ID: 004
Revises: 003
Create Date: 2026-04-01
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None

SCHEMA = "nexagent"


def upgrade() -> None:
    # executions
    op.create_table(
        "executions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workflow_id", postgresql.UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.workflows.id", ondelete="SET NULL"), nullable=True),
        sa.Column("task_input", sa.Text(), nullable=False),
        sa.Column("final_output", sa.Text(), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_cost_usd", sa.Numeric(10, 6), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'cancelled')",
            name="ck_executions_execution_status_valid",
        ),
        schema=SCHEMA,
    )
    op.create_index("idx_executions_workflow", "executions", ["workflow_id"], schema=SCHEMA)
    op.create_index("idx_executions_status", "executions", ["status"], schema=SCHEMA)

    # execution_lanes
    op.create_table(
        "execution_lanes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("execution_id", postgresql.UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.executions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lane_index", sa.Integer(), nullable=False),
        sa.Column("actor_type", sa.String(30), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_name", sa.String(255), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("execution_id", "lane_index", name="uq_execution_lanes_exec_lane"),
        sa.CheckConstraint(
            "actor_type IN ('master', 'sub_agent')",
            name="ck_execution_lanes_lane_actor_type_valid",
        ),
        schema=SCHEMA,
    )

    # execution_steps
    op.create_table(
        "execution_steps",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("lane_id", postgresql.UUID(as_uuid=True), sa.ForeignKey(f"{SCHEMA}.execution_lanes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_index", sa.Integer(), nullable=False),
        sa.Column("step_type", sa.String(30), nullable=False),
        sa.Column("input_data", postgresql.JSONB(), nullable=True),
        sa.Column("output_data", postgresql.JSONB(), nullable=True),
        sa.Column("model_used", sa.String(255), nullable=True),
        sa.Column("tokens_prompt", sa.Integer(), nullable=True),
        sa.Column("tokens_completion", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="running"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("lane_id", "step_index", name="uq_execution_steps_lane_step"),
        sa.CheckConstraint(
            "step_type IN ('llm_call', 'tool_call', 'delegation', 'synthesis', 'error')",
            name="ck_execution_steps_step_type_valid",
        ),
        schema=SCHEMA,
    )
    op.create_index("idx_execution_steps_lane", "execution_steps", ["lane_id"], schema=SCHEMA)


def downgrade() -> None:
    op.drop_table("execution_steps", schema=SCHEMA)
    op.drop_table("execution_lanes", schema=SCHEMA)
    op.drop_table("executions", schema=SCHEMA)
