"""Sub-agent runner — isolated ReAct loop per sub-agent."""

from __future__ import annotations

import time
import logging
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, BaseMessage
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic

from nexagent.engine.tool_executor import resolve_tools
from nexagent.models.sub_agent import SubAgent
from nexagent.services.crypto import decrypt_api_key

logger = logging.getLogger(__name__)

MAX_REACT_STEPS = 15  # Hard ceiling to prevent infinite loops


def _build_llm(agent: SubAgent) -> Any:
    """Dynamically build an LLM instance from sub-agent config."""
    api_key = ""
    if agent.api_key_encrypted:
        api_key = decrypt_api_key(agent.api_key_encrypted)

    kwargs: dict[str, Any] = {
        "model": agent.model_name,
        "temperature": agent.temperature,
    }
    if agent.max_tokens:
        kwargs["max_tokens"] = agent.max_tokens

    provider = agent.provider.lower()

    if provider in ("openai", "litellm", "custom"):
        if api_key:
            kwargs["api_key"] = api_key
        config = agent.config or {}
        if config.get("base_url"):
            kwargs["base_url"] = config["base_url"]
        return ChatOpenAI(**kwargs)
    elif provider == "anthropic":
        if api_key:
            kwargs["api_key"] = api_key
        return ChatAnthropic(**kwargs)
    else:
        # Fallback: assume OpenAI-compatible interface
        if api_key:
            kwargs["api_key"] = api_key
        return ChatOpenAI(**kwargs)


async def run_sub_agent(
    agent: SubAgent,
    sub_task: str,
) -> dict[str, Any]:
    """Run a sub-agent's ReAct loop with its bound tools.

    Returns:
        {
            "output": str,
            "tool_calls_log": list[dict],
            "tokens_used": int,
            "duration_ms": int,
        }
    """
    start = time.monotonic()
    tools = resolve_tools(list(agent.tools))
    llm = _build_llm(agent)

    # Build tool map for execution
    tool_map: dict[str, Any] = {t.name: t for t in tools}

    # Bind tools to LLM if any are available
    if tools:
        bound_llm = llm.bind_tools(tools)
    else:
        bound_llm = llm

    # Build initial messages
    messages: list[BaseMessage] = []
    if agent.system_prompt:
        from langchain_core.messages import SystemMessage
        messages.append(SystemMessage(content=agent.system_prompt))
    messages.append(HumanMessage(content=sub_task))

    tool_calls_log: list[dict[str, Any]] = []
    total_tokens = 0

    for _step in range(MAX_REACT_STEPS):
        try:
            response: AIMessage = await bound_llm.ainvoke(messages)
        except Exception as e:
            logger.error("LLM call failed for sub-agent '%s': %s", agent.name, e)
            elapsed = int((time.monotonic() - start) * 1000)
            return {
                "output": f"LLM error: {e}",
                "tool_calls_log": tool_calls_log,
                "tokens_used": total_tokens,
                "duration_ms": elapsed,
                "error": str(e),
            }

        # Accumulate tokens from usage_metadata
        usage = getattr(response, "usage_metadata", None)
        if usage:
            total_tokens += (usage.get("input_tokens", 0) + usage.get("output_tokens", 0))

        messages.append(response)

        # If no tool calls, we're done
        if not response.tool_calls:
            elapsed = int((time.monotonic() - start) * 1000)
            return {
                "output": response.content or "",
                "tool_calls_log": tool_calls_log,
                "tokens_used": total_tokens,
                "duration_ms": elapsed,
            }

        # Execute tool calls
        from langchain_core.messages import ToolMessage

        for tc in response.tool_calls:
            tool_name = tc["name"]
            tool_args = tc["args"]
            tool_calls_log.append({"tool": tool_name, "args": tool_args})

            tool_fn = tool_map.get(tool_name)
            if tool_fn is None:
                result_str = f"Error: tool '{tool_name}' not available"
            else:
                try:
                    result = await tool_fn.ainvoke(tool_args)
                    result_str = str(result)
                except Exception as e:
                    logger.warning("Tool '%s' failed: %s", tool_name, e)
                    result_str = f"Tool error: {e}"

            messages.append(
                ToolMessage(content=result_str, tool_call_id=tc["id"])
            )

    # Exhausted steps
    elapsed = int((time.monotonic() - start) * 1000)
    last_content = messages[-1].content if messages else "Max steps reached"
    return {
        "output": str(last_content),
        "tool_calls_log": tool_calls_log,
        "tokens_used": total_tokens,
        "duration_ms": elapsed,
    }
