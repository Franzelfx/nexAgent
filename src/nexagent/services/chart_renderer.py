"""HTTP client for nxpChartRenderer service."""
from __future__ import annotations

from typing import Any

import httpx

from nexagent.config import settings

_TIMEOUT = 60.0


async def render_chart(
    chart_type: str,
    data: list[dict[str, Any]],
    config: dict[str, Any] | None = None,
    width: int = 800,
    height: int = 450,
    fmt: str = "png",
) -> str:
    """Render a chart and return a base64 data URI."""
    payload = {
        "spec": {
            "chart_type": chart_type,
            "data": data,
            "config": config or {},
            "width": width,
            "height": height,
            "format": fmt,
        }
    }
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(f"{settings.chart_renderer_url}/render", json=payload)
        resp.raise_for_status()
        return resp.json()["data_uri"]


async def render_batch(
    specs: list[dict[str, Any]],
) -> list[str]:
    """Batch render multiple charts, return list of data URIs."""
    payload = {"items": specs}
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(f"{settings.chart_renderer_url}/render/batch", json=payload)
        resp.raise_for_status()
        return [r["data_uri"] for r in resp.json()["results"]]


async def render_thumbnail(
    specs: list[dict[str, Any]],
    thumb_width: int = 400,
    thumb_height: int = 225,
) -> bytes:
    """Render 2×2 thumbnail composite, return raw PNG bytes."""
    payload = {"items": specs[:4], "thumb_width": thumb_width, "thumb_height": thumb_height}
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(f"{settings.chart_renderer_url}/render/thumbnail", json=payload)
        resp.raise_for_status()
        return resp.content


async def health_check() -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.get(f"{settings.chart_renderer_url}/health")
        resp.raise_for_status()
        return resp.json()
