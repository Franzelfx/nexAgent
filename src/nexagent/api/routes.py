"""API routes."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from langchain_core.messages import HumanMessage

from nexagent.graphs import graph
from nexagent.state import AgentState

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    thread_id: str | None = None


class ChatResponse(BaseModel):
    reply: str
    tool_calls_log: list[dict]


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    """Run the agent graph with a user message and return the final response."""
    initial_state = AgentState(messages=[HumanMessage(content=req.message)])
    result = await graph.ainvoke(initial_state)
    last_msg = result["messages"][-1]
    return ChatResponse(
        reply=last_msg.content,
        tool_calls_log=result.get("tool_calls_log", []),
    )
