"""Canvas chart render endpoints (Epic 8)."""
from __future__ import annotations

import base64
import io
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from nexagent.schemas.canvas_chart import (
    CanvasChartNode,
    CanvasChartRenderRequest,
    CanvasExportRequest,
)
from nexagent.services.chart_renderer import render_chart

router = APIRouter(prefix="/api/v1/canvas", tags=["canvas"])


@router.post("/chart/render", summary="Render a canvas chart node on placement (Epic 8.2)")
async def canvas_render(req: CanvasChartRenderRequest) -> dict[str, Any]:
    """Render chart node, switching to SVG when zoom > 1.5x (Epic 8.3)."""
    node = req.node
    fmt = "svg" if req.zoom > 1.5 else "png"

    # Resolve inline data (execution_query / pipeline_query fetching is out of scope here)
    data = node.data_source.data

    try:
        uri = await render_chart(
            chart_type=node.chart_type,
            data=data,
            config=node.chart_config,
            width=node.size.get("width", 800),
            height=node.size.get("height", 450),
            fmt=fmt,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Renderer error: {exc}") from exc

    return {
        "node_id": node.node_id,
        "data_uri": uri,
        "format": fmt,
    }


@router.post("/export", summary="Compose canvas export image (Epic 8.6)")
async def canvas_export(req: CanvasExportRequest) -> Response:
    """Render all chart nodes and compose them into a single canvas image."""
    try:
        from PIL import Image
    except ModuleNotFoundError as exc:
        raise HTTPException(status_code=503, detail="Pillow is not installed") from exc

    composite = Image.new(
        "RGB",
        (req.canvas_width, req.canvas_height),
        _parse_color(req.background_color),
    )

    for node in req.nodes:
        data = node.data_source.data
        try:
            uri = await render_chart(
                chart_type=node.chart_type,
                data=data,
                config=node.chart_config,
                width=node.size.get("width", 800),
                height=node.size.get("height", 450),
                fmt="png",
            )
            raw = base64.b64decode(uri.split(",", 1)[1])
            tile = Image.open(io.BytesIO(raw)).convert("RGB")
            x = int(node.position.get("x", 0))
            y = int(node.position.get("y", 0))
            composite.paste(tile, (x, y))
        except Exception:
            pass  # Skip failed tiles; don't abort the whole export

    buf = io.BytesIO()
    composite.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png")


def _parse_color(hex_color: str) -> tuple[int, int, int]:
    hex_color = hex_color.strip("#")
    if len(hex_color) == 6:
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        return r, g, b
    return (26, 31, 46)
