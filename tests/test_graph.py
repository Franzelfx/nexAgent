"""Smoke test — verify graph compiles and has expected nodes."""

from nexagent.graphs import graph


def test_graph_compiles() -> None:
    assert graph is not None


def test_graph_has_expected_nodes() -> None:
    node_names = set(graph.nodes.keys())
    assert "agent" in node_names
    assert "tools" in node_names
