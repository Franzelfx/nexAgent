"""Resolve tool_definitions from DB into LangChain callables at runtime."""

from __future__ import annotations

import ast
import textwrap
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


# ── Allowed builtins for sandboxed function execution ──
_SAFE_BUILTINS = {
    "abs", "all", "any", "bool", "dict", "enumerate", "filter",
    "float", "frozenset", "int", "isinstance", "len", "list",
    "map", "max", "min", "print", "range", "round", "set",
    "sorted", "str", "sum", "tuple", "type", "zip",
}

# Allowed imports (module prefixes)
_SAFE_IMPORTS = {
    "json", "math", "datetime", "hashlib", "re", "collections",
    "itertools", "functools", "statistics", "textwrap", "urllib.parse",
}


def _make_function_tool(td: ToolDefinition) -> StructuredTool:
    """Create a tool that executes user-defined Python code in a restricted sandbox.

    The config must contain a `code` field with a Python function body.
    The function receives kwargs and must return a string.
    """
    config = td.config or {}
    code = config.get("code", "")

    if not code.strip():
        async def _empty(**kwargs: Any) -> str:
            return f"Function tool '{td.name}' has no code configured."
        return StructuredTool.from_function(
            coroutine=_empty, name=td.name, description=td.description, args_schema=None,
        )

    # Validate syntax at registration time (fail fast)
    try:
        tree = ast.parse(code, mode="exec")
    except SyntaxError as e:
        raise ValueError(f"Function tool '{td.name}' has invalid syntax: {e}") from e

    # Block dangerous patterns
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if not any(alias.name.startswith(safe) for safe in _SAFE_IMPORTS):
                    raise ValueError(f"Import '{alias.name}' is not allowed in function tool '{td.name}'")
        elif isinstance(node, ast.ImportFrom):
            if node.module and not any(node.module.startswith(safe) for safe in _SAFE_IMPORTS):
                raise ValueError(f"Import from '{node.module}' is not allowed in function tool '{td.name}'")

    async def _exec_fn(**kwargs: Any) -> str:
        # Compile in restricted namespace
        safe_globals: dict[str, Any] = {"__builtins__": {k: __builtins__[k] for k in _SAFE_BUILTINS if k in __builtins__}} if isinstance(__builtins__, dict) else {}
        safe_globals["__builtins__"] = {k: getattr(__builtins__, k, None) for k in _SAFE_BUILTINS}
        # Allow safe imports
        import importlib
        def _safe_import(name: str, *args: Any, **kw: Any) -> Any:
            if not any(name.startswith(safe) for safe in _SAFE_IMPORTS):
                raise ImportError(f"Import '{name}' is not allowed")
            return importlib.import_module(name)
        safe_globals["__builtins__"]["__import__"] = _safe_import

        local_ns: dict[str, Any] = {"kwargs": kwargs, **kwargs}
        exec(compile(code, f"<tool:{td.name}>", "exec"), safe_globals, local_ns)

        # Look for a callable named 'run' or 'execute' or the tool name
        for fn_name in ("run", "execute", td.name):
            if fn_name in local_ns and callable(local_ns[fn_name]):
                result = local_ns[fn_name](**kwargs)
                return str(result)

        # If no function found, return last assigned variable or empty
        return str(local_ns.get("result", "Function executed but no 'run()' function or 'result' variable found."))

    return StructuredTool.from_function(
        coroutine=_exec_fn,
        name=td.name,
        description=td.description,
        args_schema=None,
    )


def _make_mcp_tool(td: ToolDefinition) -> StructuredTool:
    """Create a tool that calls an MCP server endpoint."""
    config = td.config or {}
    server_url = config.get("server_url", "")
    tool_name = config.get("tool_name", td.name)
    timeout = config.get("timeout", 30)

    if not server_url:
        async def _no_url(**kwargs: Any) -> str:
            return f"MCP tool '{td.name}' has no server_url configured."
        return StructuredTool.from_function(
            coroutine=_no_url, name=td.name, description=td.description, args_schema=None,
        )

    async def _mcp_call(**kwargs: Any) -> str:
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": kwargs},
            "id": 1,
        }
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(server_url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            if "error" in data:
                return f"MCP error: {data['error']}"
            result = data.get("result", {})
            # MCP returns content array
            content = result.get("content", [])
            texts = [c.get("text", str(c)) for c in content if isinstance(c, dict)]
            return "\n".join(texts) if texts else str(result)

    return StructuredTool.from_function(
        coroutine=_mcp_call,
        name=td.name,
        description=td.description,
        args_schema=None,
    )


def resolve_tools(tool_definitions: list[ToolDefinition]) -> list[Any]:
    """Convert a list of ToolDefinition ORM objects into LangChain tool callables.

    Supported types:
    - builtin: maps to Python functions registered in tools/__init__.py
    - api_call: makes HTTP requests based on tool config
    - function: executes user-defined Python code in a sandboxed environment
    - mcp: calls an MCP server via JSON-RPC

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
        elif td.tool_type == "function":
            resolved.append(_make_function_tool(td))
        elif td.tool_type == "mcp":
            resolved.append(_make_mcp_tool(td))
        else:
            raise ValueError(f"Unknown tool type '{td.tool_type}' for tool '{td.name}'")

    return resolved
