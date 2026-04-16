"""FastAPI wrapper to serve the LangGraph agent + health endpoint."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from nexagent.api.routes import router
from nexagent.config import settings
from nexagent.database import ensure_schema
from nexagent.services.builtin_sync import sync_builtin_tools


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    # Startup
    await ensure_schema()
    await sync_builtin_tools()
    yield
    # Shutdown


app = FastAPI(
    title="NexAgent API",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

# v1 API routers
from nexagent.api.executions_router import router as executions_router  # noqa: E402
from nexagent.api.orchestrators_router import router as orchestrators_router  # noqa: E402
from nexagent.api.sub_agents_router import router as sub_agents_router  # noqa: E402
from nexagent.api.tools_router import router as tools_router  # noqa: E402
from nexagent.api.workflows_router import router as workflows_router  # noqa: E402

app.include_router(tools_router)
app.include_router(sub_agents_router)
app.include_router(orchestrators_router)
app.include_router(workflows_router)
app.include_router(executions_router)

from nexagent.api.dashboard_router import router as dashboard_router  # noqa: E402
from nexagent.api.canvas_router import router as canvas_router  # noqa: E402

app.include_router(dashboard_router)
app.include_router(canvas_router)
