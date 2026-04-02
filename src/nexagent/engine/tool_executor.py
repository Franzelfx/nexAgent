"""Resolve tool_definitions from DB into LangChain callables at runtime."""

from __future__ import annotations

from typing import Any

import httpx
from langchain_core.tools import StructuredTool, tool

from nexagent.models.tool_definition import ToolDefinition
from nexagent.tools import ALL_TOOLS

# Cache: tool_name → callable (populated per execution)
_builtin_registry: dict[str, Any] = {}


def _ensure_builtin_registry() -> dict[str, Any]:
    """Lazily build a name→callable map of built-in tools."""
    if not _builtin_registry:
        for t in ALL_TOOLS:
            _builtin_registry[t.name] = t
    return _builtin_registry


def _make_api_call_tool(td: ToolDefinition) -> StructuredTool:
    """Create a LangChain tool that performs an HTTP call based on tool config."""
    config = td.config or {}
    url = config.get("url", "")
    method = config.get("method", "POST").upper()
    headers = config.get("headers", {})
    timeout = config.get("timeout", 30)

    async def _call(**kwargs: Any) -> str:
        async with httpx.AsyncClient(timeout=timeout) as client:
            if method == "GET":
                resp = await client.get(url, params=kwargs, headers=headers)
            else:
                resp = await client.request(method, url, json=kwargs, headers=headers)
            resp.raise_for_status()
            return resp.text

    return StructuredTool.from_function(
        coroutine=_call,
        name=td.name,
        description=td.description,
        args_schema=None,
    )


def _make_stub_tool(td: ToolDefinition, tool_type: str) -> StructuredTool:
    """Create a stub tool for not-yet-implemented types (function, mcp)."""

    async def _stub(**kwargs: Any) -> str:
        return f"Tool type '{tool_type}' is not yet implemented for '{td.name}'."

    return StructuredTool.from_function(
        coroutine=_stub,
        name=td.name,
        description=td.description,
        args_schema=None,
    )


def resolve_tools(tool_definitions: list[ToolDefinition]) -> list[Any]:
    """Convert a list of ToolDefinition ORM objects into LangChain tool callables.

    Supported types:
    - builtin: maps to Python functions registered in tools/__init__.py
    - api_call: makes HTTP requests based on tool config
    - function / mcp: stubs (not yet implemented)

    Returns a list of LangChain-compatible tools.
    """
    registry = _ensure_builtin_registry()
    resolved: list[Any] = []

    for td in tool_definitions:
        if td.tool_type == "builtin":
            builtin = registry.get(td.name)
            if builtin is None:
                raise ValueError(f"Built-in tool '{td.name}' not found in registry")
            resolved.append(builtin)
        elif td.tool_type == "api_call":
            resolved.append(_make_api_call_tool(td))
        elif td.tool_type in ("function", "mcp"):
            resolved.append(_make_stub_tool(td, td.tool_type))
        else:
            raise ValueError(f"Unknown tool type '{td.tool_type}' for tool '{td.name}'")

    return resolved
