"""Tests for S3/S4 ORM models (import, schema, relationships)."""

from __future__ import annotations

from nexagent.models import Base, Orchestrator, SubAgent, ToolDefinition, Workflow
from nexagent.models.base import SCHEMA


def test_all_tables_in_metadata():
    table_names = set(Base.metadata.tables.keys())
    expected = {
        f"{SCHEMA}.tool_definitions",
        f"{SCHEMA}.sub_agents",
        f"{SCHEMA}.sub_agent_tools",
        f"{SCHEMA}.orchestrators",
        f"{SCHEMA}.orchestrator_sub_agents",
        f"{SCHEMA}.workflows",
    }
    assert expected.issubset(table_names)


def test_sub_agent_columns():
    cols = {c.name for c in SubAgent.__table__.columns}
    for col in ("id", "name", "role_description", "provider", "model_name", "api_key_encrypted",
                "temperature", "max_tokens", "config", "is_active", "created_at", "updated_at"):
        assert col in cols, f"Missing column: {col}"


def test_orchestrator_columns():
    cols = {c.name for c in Orchestrator.__table__.columns}
    for col in ("id", "name", "provider", "model_name", "strategy", "max_iterations",
                "api_key_encrypted", "config", "is_active"):
        assert col in cols, f"Missing column: {col}"


def test_workflow_columns():
    cols = {c.name for c in Workflow.__table__.columns}
    for col in ("id", "name", "orchestrator_id", "graph_layout", "is_active"):
        assert col in cols, f"Missing column: {col}"


def test_sub_agent_has_tools_relationship():
    assert hasattr(SubAgent, "tools")


def test_orchestrator_has_sub_agents_relationship():
    assert hasattr(Orchestrator, "sub_agents")


def test_workflow_has_orchestrator_relationship():
    assert hasattr(Workflow, "orchestrator")
