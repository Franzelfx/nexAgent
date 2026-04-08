"""Built-in example tools for the agent."""

from __future__ import annotations

import os

from langchain_core.tools import tool


@tool
def get_current_time() -> str:
    """Return the current UTC time. Useful for time-aware tasks."""
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


@tool
def calculator(expression: str) -> str:
    """Evaluate a mathematical expression safely and return the result.

    Args:
        expression: A mathematical expression like '2 + 2' or '(3 * 4) / 2'.
    """
    import ast
    import operator as op

    allowed_ops = {
        ast.Add: op.add,
        ast.Sub: op.sub,
        ast.Mult: op.mul,
        ast.Div: op.truediv,
        ast.Pow: op.pow,
        ast.USub: op.neg,
        ast.Mod: op.mod,
    }

    def _eval(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.BinOp) and type(node.op) in allowed_ops:
            return allowed_ops[type(node.op)](_eval(node.left), _eval(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in allowed_ops:
            return allowed_ops[type(node.op)](_eval(node.operand))
        raise ValueError(f"Unsupported expression: {ast.dump(node)}")

    tree = ast.parse(expression, mode="eval")
    result = _eval(tree)
    return str(result)


# ── Pipeline-aware tools ──────────────────────────────────
_CONFIGHEAD_URL = os.getenv("CONFIGHEAD_URL", "http://nxp-confighead:8002")


@tool
def list_pipelines() -> str:
    """List all available data pipelines with their status and node count.

    Returns a summary of pipelines in the warehouse.
    """
    import httpx

    try:
        resp = httpx.get(
            f"{_CONFIGHEAD_URL}/v1/ingest/pipeline",
            timeout=15,
        )
        resp.raise_for_status()
        pipelines = resp.json()
        if not pipelines:
            return "No pipelines found."
        lines = []
        for p in pipelines:
            lines.append(
                f"- {p.get('name', '?')} (id={p.get('id', '?')}, "
                f"status={p.get('status', '?')}, "
                f"nodes={p.get('node_count', 0)}, "
                f"edges={p.get('edge_count', 0)})"
            )
        return f"Found {len(pipelines)} pipelines:\n" + "\n".join(lines)
    except Exception as e:
        return f"Error listing pipelines: {e}"


@tool
def get_pipeline_details(pipeline_id: str) -> str:
    """Get detailed information about a specific pipeline including all nodes and edges.

    Args:
        pipeline_id: The UUID of the pipeline to inspect.
    """
    import httpx

    try:
        resp = httpx.get(
            f"{_CONFIGHEAD_URL}/v1/ingest/pipeline/{pipeline_id}",
            timeout=15,
        )
        resp.raise_for_status()
        p = resp.json()
        lines = [
            f"Pipeline: {p.get('name', '?')}",
            f"Status: {p.get('status', '?')}",
            f"Nodes: {p.get('node_count', 0)}, Edges: {p.get('edge_count', 0)}",
            f"Description: {p.get('description', 'N/A')}",
        ]
        return "\n".join(lines)
    except Exception as e:
        return f"Error getting pipeline: {e}"


@tool
def validate_pipeline(pipeline_id: str) -> str:
    """Validate a pipeline's topology — check edge rules, orphan nodes, and terminal presence.

    Args:
        pipeline_id: The UUID of the pipeline to validate.
    """
    import httpx

    try:
        resp = httpx.get(
            f"{_CONFIGHEAD_URL}/v1/ingest/pipeline/{pipeline_id}/validate",
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        valid = data.get("valid", False)
        errors = data.get("errors", [])
        warnings = data.get("warnings", [])
        lines = [f"Valid: {'✓' if valid else '✗'}"]
        if errors:
            lines.append(f"Errors ({len(errors)}):")
            for e in errors:
                lines.append(f"  - [{e.get('type')}] {e.get('message')}")
        if warnings:
            lines.append(f"Warnings ({len(warnings)}):")
            for w in warnings:
                lines.append(f"  - [{w.get('type')}] {w.get('message')}")
        if not errors and not warnings:
            lines.append("No issues found — pipeline topology is healthy.")
        return "\n".join(lines)
    except Exception as e:
        return f"Error validating pipeline: {e}"


# Registry: add new tools here and they are auto-discovered by the graph
ALL_TOOLS = [
    get_current_time,
    calculator,
    list_pipelines,
    get_pipeline_details,
    validate_pipeline,
]
