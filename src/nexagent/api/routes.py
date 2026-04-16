"""API routes."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from langchain_core.messages import HumanMessage

from nexagent.database import check_db
from nexagent.graphs import graph
from nexagent.state import AgentState

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    thread_id: str | None = None


class Attachment(BaseModel):
    """A chart or file attachment produced by a tool call."""

    type: str  # "image/png", "image/svg+xml", etc.
    data_uri: str  # base64 data URI
    title: str = ""


class ChatResponse(BaseModel):
    reply: str
    tool_calls_log: list[dict]
    attachments: list[Attachment] = []


@router.get("/health")
async def health() -> dict:
    db_ok = await check_db()
    return {"status": "ok" if db_ok else "degraded", "db": "ok" if db_ok else "unreachable"}


@router.get("/studio")
async def studio(request: Request) -> RedirectResponse:
    """Redirect to hosted LangGraph Studio bound to this deployment URL."""
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host", request.headers.get("host", request.url.netloc))
    base_url = f"{proto}://{host}".rstrip("/")
    target = f"https://smith.langchain.com/studio/?baseUrl={base_url}"
    return RedirectResponse(url=target, status_code=307)


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    """Run the agent graph with a user message and return the final response."""
    initial_state = AgentState(messages=[HumanMessage(content=req.message)])
    result = await graph.ainvoke(initial_state)
    last_msg = result["messages"][-1]

    # Extract chart attachments produced by render_* tools
    attachments: list[Attachment] = []
    for log_entry in result.get("tool_calls_log", []):
        output = log_entry.get("output", "")
        if isinstance(output, str) and output.startswith("data:image/"):
            mime = output.split(";", 1)[0].split(":", 1)[1]
            attachments.append(Attachment(type=mime, data_uri=output,
                                          title=log_entry.get("tool", "")))

    return ChatResponse(
        reply=last_msg.content,
        tool_calls_log=result.get("tool_calls_log", []),
        attachments=attachments,
    )
