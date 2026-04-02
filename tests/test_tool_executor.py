"""Tests for the tool executor (S5.4)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from nexagent.engine.tool_executor import resolve_tools, _ensure_builtin_registry


def _make_td(**kwargs) -> SimpleNamespace:
    """Create a ToolDefinition-like object for testing (avoids SQLAlchemy instrumentation)."""
    return SimpleNamespace(
        name=kwargs.get("name", "test_tool"),
        description=kwargs.get("description", "A test tool"),
        tool_type=kwargs.get("tool_type", "builtin"),
        config=kwargs.get("config", {}),
        input_schema=kwargs.get("input_schema", {}),
        output_schema=kwargs.get("output_schema", None),
        is_active=kwargs.get("is_active", True),
    )


class TestToolExecutor:
    def test_builtin_registry_populated(self):
        registry = _ensure_builtin_registry()
        assert "get_current_time" in registry
        assert "calculator" in registry

    def test_resolve_builtin_tool(self):
        td = _make_td(name="get_current_time", tool_type="builtin")
        tools = resolve_tools([td])
        assert len(tools) == 1
        assert tools[0].name == "get_current_time"

    def test_resolve_unknown_builtin_raises(self):
        td = _make_td(name="nonexistent_builtin", tool_type="builtin")
        with pytest.raises(ValueError, match="not found in registry"):
            resolve_tools([td])

    def test_resolve_api_call_tool(self):
        td = _make_td(
            name="weather_api",
            tool_type="api_call",
            description="Get weather data",
            config={"url": "https://api.example.com/weather", "method": "GET"},
        )
        tools = resolve_tools([td])
        assert len(tools) == 1
        assert tools[0].name == "weather_api"

    def test_resolve_function_stub(self):
        td = _make_td(name="custom_fn", tool_type="function", description="Custom function")
        tools = resolve_tools([td])
        assert len(tools) == 1
        assert tools[0].name == "custom_fn"

    def test_resolve_mcp_stub(self):
        td = _make_td(name="mcp_tool", tool_type="mcp", description="MCP tool")
        tools = resolve_tools([td])
        assert len(tools) == 1
        assert tools[0].name == "mcp_tool"

    def test_resolve_unknown_type_raises(self):
        td = _make_td(name="bad_tool", tool_type="alien")
        with pytest.raises(ValueError, match="Unknown tool type"):
            resolve_tools([td])

    def test_resolve_multiple_tools(self):
        tds = [
            _make_td(name="get_current_time", tool_type="builtin"),
            _make_td(name="calculator", tool_type="builtin"),
        ]
        tools = resolve_tools(tds)
        assert len(tools) == 2

    @pytest.mark.asyncio
    async def test_stub_tool_returns_not_implemented(self):
        td = _make_td(name="future_fn", tool_type="function", description="Future function")
        tools = resolve_tools([td])
        result = await tools[0].ainvoke({})
        assert "not yet implemented" in result
