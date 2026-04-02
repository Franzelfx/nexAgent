"""Test that all models import correctly and register with Base.metadata."""

from nexagent.models import Base, ToolDefinition
from nexagent.models.base import SCHEMA


def test_base_schema() -> None:
    assert Base.metadata.schema == SCHEMA


def test_tool_definition_in_metadata() -> None:
    table_names = [t.name for t in Base.metadata.sorted_tables]
    assert "tool_definitions" in table_names


def test_tool_definition_columns() -> None:
    cols = {c.name for c in ToolDefinition.__table__.columns}
    expected = {
        "id", "name", "display_name", "description", "tool_type",
        "input_schema", "output_schema", "config", "is_active",
        "created_at", "updated_at",
    }
    assert expected.issubset(cols)


def test_packages_importable() -> None:
    """Verify all new packages import without error."""
    import nexagent.models
    import nexagent.schemas
    import nexagent.services
    import nexagent.engine
    import nexagent.database
