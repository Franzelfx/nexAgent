"""Dashboard render endpoints — proxy to nxpChartRenderer (Epic 6)."""
from __future__ import annotations

import base64
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from nexagent.services.chart_renderer import (
    health_check,
    render_batch,
    render_chart,
    render_thumbnail,
)

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


class DashboardRenderRequest(BaseModel):
    chart_type: str = "timeseries"
    data: list[dict[str, Any]] = Field(default_factory=list)
    config: dict[str, Any] = Field(default_factory=dict)
    width: int = 800
    height: int = 450
    format: str = "png"


class DashboardRenderResponse(BaseModel):
    data_uri: str


class BatchDashboardRequest(BaseModel):
    items: list[DashboardRenderRequest] = Field(max_length=20)


class BatchDashboardResponse(BaseModel):
    data_uris: list[str]


@router.post("/render", response_model=DashboardRenderResponse,
             summary="Render a single dashboard chart (Epic 6.1)")
async def dashboard_render(req: DashboardRenderRequest) -> DashboardRenderResponse:
    try:
        uri = await render_chart(
            chart_type=req.chart_type,
            data=req.data,
            config=req.config,
            width=req.width,
            height=req.height,
            fmt=req.format,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Renderer error: {exc}") from exc
    return DashboardRenderResponse(data_uri=uri)


@router.post("/render/batch", response_model=BatchDashboardResponse,
             summary="Batch dashboard render (Epic 6.2)")
async def dashboard_render_batch(req: BatchDashboardRequest) -> BatchDashboardResponse:
    specs = [
        {
            "chart_type": item.chart_type,
            "data": item.data,
            "config": item.config,
            "width": item.width,
            "height": item.height,
            "format": item.format,
        }
        for item in req.items
    ]
    try:
        uris = await render_batch(specs)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Renderer error: {exc}") from exc
    return BatchDashboardResponse(data_uris=uris)


@router.post("/thumbnail", summary="2×2 composite thumbnail (Epic 6.3)")
async def dashboard_thumbnail(req: BatchDashboardRequest) -> Response:
    specs = [
        {
            "chart_type": item.chart_type,
            "data": item.data,
            "config": item.config,
        }
        for item in req.items[:4]
    ]
    try:
        png = await render_thumbnail(specs)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Renderer error: {exc}") from exc
    return Response(content=png, media_type="image/png")


@router.get("/render/health", summary="Chart renderer health")
async def renderer_health() -> dict[str, Any]:
    try:
        return await health_check()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
