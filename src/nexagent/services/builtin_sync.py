"""Sync built-in tools from code into the database on startup."""

from __future__ import annotations

import logging

from sqlalchemy import select

from nexagent.database import async_session
from nexagent.models.tool_definition import ToolDefinition

logger = logging.getLogger(__name__)

# Registry of built-in tools to seed into the database.
# Each entry maps to a function in nexagent.tools and is auto-synced on startup.
BUILTIN_TOOLS: list[dict] = [
    {
        "name": "get_current_time",
        "display_name": "Get Current Time",
        "description": "Return the current UTC time. Useful for time-aware tasks.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "calculator",
        "display_name": "Calculator",
        "description": "Evaluate a mathematical expression safely and return the result.",
        "input_schema": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "A mathematical expression like '2 + 2' or '(3 * 4) / 2'.",
                }
            },
            "required": ["expression"],
        },
    },
]


async def sync_builtin_tools() -> None:
    """Upsert all built-in tool definitions into the database.

    Idempotent — safe to call on every startup.
    """
    async with async_session() as db:
        for tool_data in BUILTIN_TOOLS:
            result = await db.execute(
                select(ToolDefinition).where(ToolDefinition.name == tool_data["name"])
            )
            existing = result.scalar_one_or_none()

            if existing is None:
                tool = ToolDefinition(
                    name=tool_data["name"],
                    display_name=tool_data["display_name"],
                    description=tool_data["description"],
                    tool_type="builtin",
                    input_schema=tool_data["input_schema"],
                )
                db.add(tool)
                logger.info("Registered built-in tool: %s", tool_data["name"])
            else:
                # Update description/schema if the code definition changed
                existing.display_name = tool_data["display_name"]
                existing.description = tool_data["description"]
                existing.input_schema = tool_data["input_schema"]
                existing.tool_type = "builtin"

        await db.commit()
