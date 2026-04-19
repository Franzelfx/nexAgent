"""Pipeline output emit buffer (Epic 7).

The orchestrator (and its sub-agents) may call the reserved tool
`emit_pipeline_output` to hand structured data back to the pipeline that invoked
them. Since the LangChain ReAct loop runs in a sub-agent runner without direct
access to the execution record, each execution owns a process-local buffer
addressed by `execution_id`. The sub_agent_runner intercepts tool calls by name
and appends to the buffer instead of invoking a real callable. The master
runner collects the buffer when the execution completes and persists it on the
`executions.emit_buffer` column.

Payload shape — enforced lightly (missing fields default to None):

    {
        "kind": "rows" | "timeseries" | "indexed_text",
        "payload": <any JSON-serializable value>,
        "name": <optional stream name>,
        "meta": <optional dict>,
    }
"""

from __future__ import annotations

import threading
import uuid
from typing import Any

RESERVED_TOOL_NAME = "emit_pipeline_output"
ALLOWED_KINDS = {"rows", "timeseries", "indexed_text"}

_buffers: dict[uuid.UUID, list[dict[str, Any]]] = {}
_lock = threading.Lock()


def start(execution_id: uuid.UUID) -> None:
    """Initialise an empty buffer for this execution."""
    with _lock:
        _buffers[execution_id] = []


def append(execution_id: uuid.UUID, emit: dict[str, Any]) -> None:
    """Append a single emit payload. Called by the tool intercept."""
    if execution_id is None:
        return
    with _lock:
        bucket = _buffers.get(execution_id)
        if bucket is None:
            bucket = []
            _buffers[execution_id] = bucket
        bucket.append(emit)


def collect(execution_id: uuid.UUID) -> list[dict[str, Any]]:
    """Return and clear the buffer for this execution."""
    with _lock:
        return _buffers.pop(execution_id, [])


def peek(execution_id: uuid.UUID) -> list[dict[str, Any]]:
    """Return a copy of the buffer without clearing it."""
    with _lock:
        return list(_buffers.get(execution_id, []))


def normalize(raw: Any) -> dict[str, Any]:
    """Coerce agent-supplied kwargs into a canonical emit dict."""
    if not isinstance(raw, dict):
        return {
            "kind": "indexed_text",
            "payload": str(raw),
            "name": None,
            "meta": None,
        }

    kind = raw.get("kind") or raw.get("type") or "indexed_text"
    if kind not in ALLOWED_KINDS:
        kind = "indexed_text"

    payload = raw.get("payload")
    if payload is None:
        payload = raw.get("data")
    if payload is None and kind == "indexed_text":
        payload = raw.get("text") or raw.get("content") or ""

    return {
        "kind": kind,
        "payload": payload,
        "name": raw.get("name"),
        "meta": raw.get("meta"),
    }
