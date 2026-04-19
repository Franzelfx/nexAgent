"""Unit tests for the pipeline output emit buffer (Epic 7)."""

from __future__ import annotations

import uuid

from nexagent.engine import emit_buffer


def test_start_and_collect_empty() -> None:
    exec_id = uuid.uuid4()
    emit_buffer.start(exec_id)
    assert emit_buffer.collect(exec_id) == []


def test_append_then_collect_clears() -> None:
    exec_id = uuid.uuid4()
    emit_buffer.start(exec_id)
    emit_buffer.append(exec_id, {"kind": "rows", "payload": [{"a": 1}]})
    emit_buffer.append(exec_id, {"kind": "indexed_text", "payload": "hi"})

    out = emit_buffer.collect(exec_id)
    assert len(out) == 2
    assert out[0]["kind"] == "rows"
    # Buffer cleared after collect
    assert emit_buffer.collect(exec_id) == []


def test_peek_does_not_clear() -> None:
    exec_id = uuid.uuid4()
    emit_buffer.start(exec_id)
    emit_buffer.append(exec_id, {"kind": "rows", "payload": []})
    assert len(emit_buffer.peek(exec_id)) == 1
    assert len(emit_buffer.peek(exec_id)) == 1


def test_normalize_coerces_unknown_kind_to_indexed_text() -> None:
    out = emit_buffer.normalize({"kind": "bogus", "payload": "x"})
    assert out["kind"] == "indexed_text"
    assert out["payload"] == "x"


def test_normalize_handles_plain_string() -> None:
    out = emit_buffer.normalize("hello")
    assert out["kind"] == "indexed_text"
    assert out["payload"] == "hello"


def test_normalize_accepts_data_alias() -> None:
    out = emit_buffer.normalize({"kind": "rows", "data": [{"a": 1}]})
    assert out["kind"] == "rows"
    assert out["payload"] == [{"a": 1}]


def test_append_without_start_still_records() -> None:
    exec_id = uuid.uuid4()
    emit_buffer.append(exec_id, {"kind": "rows", "payload": []})
    assert len(emit_buffer.collect(exec_id)) == 1
