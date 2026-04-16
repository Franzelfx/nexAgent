"""LangChain tools for chart rendering inside agent chat.

Each tool is decorated with @tool so the ReAct agent can call them,
producing base64 PNG attachments embedded in the chat response.
"""
from __future__ import annotations

import json
from typing import Any

from langchain_core.tools import tool

from nexagent.services.chart_renderer import render_batch, render_chart


# --------------------------------------------------------------------------- #
# Tool 7.1 — generic chart render
# --------------------------------------------------------------------------- #

@tool
async def render_chart_tool(
    chart_type: str,
    data: str,
    title: str = "",
    width: int = 800,
    height: int = 450,
) -> str:
    """Render a chart and return a base64 PNG data URI for embedding in chat.

    Args:
        chart_type: One of timeseries, bar, pie, scatter, candlestick, heatmap,
                    gauge, histogram, waterfall, sankey, treemap, radar, boxplot,
                    parallel, funnel, timeline, table, map, entity_network, graph, area.
        data: JSON-serialised list of dicts with column-oriented records.
        title: Optional chart title.
        width: Width in pixels (default 800, max 4096).
        height: Height in pixels (default 450, max 4096).

    Returns:
        base64 PNG data URI string.
    """
    try:
        records: list[dict[str, Any]] = json.loads(data)
    except json.JSONDecodeError as exc:
        return f"ERROR: invalid data JSON — {exc}"

    try:
        uri = await render_chart(
            chart_type=chart_type,
            data=records,
            config={"title": title} if title else {},
            width=width,
            height=height,
        )
        return uri
    except Exception as exc:
        return f"ERROR: chart render failed — {exc}"


# --------------------------------------------------------------------------- #
# Tool 7.2 — execution timeline (Gantt)
# --------------------------------------------------------------------------- #

@tool
async def render_execution_timeline(execution_id: str) -> str:
    """Render a Gantt-style execution timeline chart for the given execution ID.

    Args:
        execution_id: UUID of the workflow execution.

    Returns:
        base64 PNG data URI string.
    """
    # Import lazily to keep tool definitions lightweight
    from nexagent.services.execution_data import fetch_timeline_data  # type: ignore[import]

    try:
        rows = await fetch_timeline_data(execution_id)
    except Exception as exc:
        return f"ERROR: could not load execution {execution_id} — {exc}"

    try:
        uri = await render_chart(
            chart_type="timeline",
            data=rows,
            config={"title": f"Execution Timeline — {execution_id[:8]}"},
            width=1200,
            height=400,
        )
        return uri
    except Exception as exc:
        return f"ERROR: chart render failed — {exc}"


# --------------------------------------------------------------------------- #
# Tool 7.3 — workflow graph topology
# --------------------------------------------------------------------------- #

@tool
async def render_workflow_graph(workflow_id: str) -> str:
    """Render the topology of a workflow as a force-directed graph.

    Args:
        workflow_id: UUID of the workflow.

    Returns:
        base64 PNG data URI string.
    """
    from nexagent.services.workflow_data import fetch_workflow_edges  # type: ignore[import]

    try:
        edges = await fetch_workflow_edges(workflow_id)
    except Exception as exc:
        return f"ERROR: could not load workflow {workflow_id} — {exc}"

    try:
        uri = await render_chart(
            chart_type="entity_network",
            data=edges,
            config={"title": f"Workflow Graph — {workflow_id[:8]}"},
            width=900,
            height=600,
        )
        return uri
    except Exception as exc:
        return f"ERROR: chart render failed — {exc}"


# --------------------------------------------------------------------------- #
# Tool 7.4 — cost / token analysis over time
# --------------------------------------------------------------------------- #

@tool
async def render_cost_analysis(
    thread_id: str = "",
    days: int = 7,
) -> str:
    """Render an aggregated cost and token usage chart.

    Args:
        thread_id: Optional thread UUID to scope to a single conversation.
        days: Number of days to look back (default 7).

    Returns:
        base64 PNG data URI string.
    """
    from nexagent.services.cost_data import fetch_cost_series  # type: ignore[import]

    try:
        rows = await fetch_cost_series(thread_id=thread_id or None, days=days)
    except Exception as exc:
        return f"ERROR: could not load cost data — {exc}"

    try:
        uri = await render_chart(
            chart_type="area",
            data=rows,
            config={"title": f"Cost Analysis (last {days}d)", "x_axis": "date",
                    "y_axis": ["total_tokens", "cost_usd"]},
            width=900,
            height=350,
        )
        return uri
    except Exception as exc:
        return f"ERROR: chart render failed — {exc}"


# --------------------------------------------------------------------------- #
# Tool 7.5 — dashboard batch render
# --------------------------------------------------------------------------- #

@tool
async def render_dashboard(specs_json: str) -> str:
    """Batch-render multiple dashboard widgets and return a composite thumbnail.

    Args:
        specs_json: JSON list of chart specs (chart_type + data per widget).

    Returns:
        base64 PNG data URI of a 2×2 composite thumbnail.
    """
    try:
        specs: list[dict[str, Any]] = json.loads(specs_json)
    except json.JSONDecodeError as exc:
        return f"ERROR: invalid specs JSON — {exc}"

    try:
        uris = await render_batch(specs[:4])
        # Return first widget's URI; caller can display all
        return "\n".join(uris)
    except Exception as exc:
        return f"ERROR: dashboard render failed — {exc}"


# --------------------------------------------------------------------------- #
# Tool registry
# --------------------------------------------------------------------------- #

CHART_TOOLS = [
    render_chart_tool,
    render_execution_timeline,
    render_workflow_graph,
    render_cost_analysis,
    render_dashboard,
]
