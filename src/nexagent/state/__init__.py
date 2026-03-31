"""Agent state definitions."""

from __future__ import annotations

import operator
from typing import Annotated, Any

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field


class AgentState(BaseModel):
    """Core state that flows through the agent graph.

    Attributes:
        messages: Chat message history (auto-merged via add_messages reducer).
        tool_calls_log: Ordered log of tool calls for tracing / visualization.
    """

    messages: Annotated[list[BaseMessage], add_messages] = Field(default_factory=list)
    tool_calls_log: Annotated[list[dict[str, Any]], operator.add] = Field(default_factory=list)
