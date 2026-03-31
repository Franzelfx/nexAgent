"""Chat agent node — calls the LLM with tools bound."""

from __future__ import annotations

from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI

from nexagent.config import settings
from nexagent.state import AgentState
from nexagent.tools import ALL_TOOLS


def _get_llm() -> ChatOpenAI:
    """Build the LLM instance from settings.

    Supports direct OpenAI, or a LiteLLM proxy (set LITELLM_BASE_URL).
    """
    kwargs: dict = {"model": settings.default_model, "temperature": 0}

    if settings.litellm_base_url:
        kwargs["base_url"] = settings.litellm_base_url
        kwargs["api_key"] = settings.litellm_api_key or "not-needed"
    elif settings.openai_api_key:
        kwargs["api_key"] = settings.openai_api_key

    return ChatOpenAI(**kwargs)


def chat_node(state: AgentState) -> dict:
    """Invoke the LLM with the current messages and bound tools."""
    llm = _get_llm().bind_tools(ALL_TOOLS)
    response: AIMessage = llm.invoke(state.messages)  # type: ignore[assignment]

    # Log tool calls for visualization
    log_entries = []
    if response.tool_calls:
        for tc in response.tool_calls:
            log_entries.append({"tool": tc["name"], "args": tc["args"]})

    return {"messages": [response], "tool_calls_log": log_entries}
