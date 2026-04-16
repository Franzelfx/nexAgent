"""Canvas chart node schemas (Epic 8)."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


DataSourceKind = Literal["inline", "execution_query", "pipeline_query"]


class DataSource(BaseModel):
    kind: DataSourceKind = "inline"
    data: list[dict[str, Any]] = Field(default_factory=list)
    # For execution_query / pipeline_query
    execution_id: str | None = None
    pipeline_id: str | None = None
    query: str | None = None


class CanvasChartNode(BaseModel):
    """Position + size + chart config for a canvas chart node (Epic 8.1)."""

    node_id: str
    position: dict[str, float]  # {"x": ..., "y": ...}
    size: dict[str, int] = Field(default_factory=lambda: {"width": 800, "height": 450})
    chart_type: str = "timeseries"
    chart_config: dict[str, Any] = Field(default_factory=dict)
    data_source: DataSource = Field(default_factory=DataSource)
    # Cached render hash from nxpChartRenderer
    render_hash: str | None = None
    # Output format hint: "png" for resting state, "svg" when zoom > 1.5x
    output_format: Literal["png", "svg"] = "png"


class CanvasChartRenderRequest(BaseModel):
    node: CanvasChartNode
    zoom: float = 1.0


class CanvasExportRequest(BaseModel):
    """Compose all chart images at their canvas positions (Epic 8.6)."""

    canvas_width: int = 1920
    canvas_height: int = 1080
    nodes: list[CanvasChartNode]
    background_color: str = "#1a1f2e"
