"""create nexagent schema

Revision ID: 001
Revises:
Create Date: 2026-04-01
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS nexagent")


def downgrade() -> None:
    op.execute("DROP SCHEMA IF EXISTS nexagent CASCADE")
