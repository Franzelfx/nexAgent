"""Main agent graph — tool-calling ReAct loop with LangGraph."""

from __future__ import annotations

from langchain_core.messages import AIMessage
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from nexagent.agents.chat import chat_node
from nexagent.state import AgentState
from nexagent.tools import ALL_TOOLS

# ── Build graph ────────────────────────────────────────────────

builder = StateGraph(AgentState)

# Nodes
builder.add_node("agent", chat_node)
builder.add_node("tools", ToolNode(ALL_TOOLS))

# Edges
builder.set_entry_point("agent")


def should_continue(state: AgentState) -> str:
    """Route: if the last AI message has tool_calls → go to tools, else → END."""
    last = state.messages[-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "tools"
    return END


builder.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
builder.add_edge("tools", "agent")

# Compile
graph = builder.compile()
