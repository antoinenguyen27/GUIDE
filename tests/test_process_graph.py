from __future__ import annotations

import pytest

from gemini.process_graph import ProcessGraph


def test_add_transition_builds_successors_and_predecessors() -> None:
    graph = ProcessGraph("kitchen_flow")
    graph.add_transition("Gather", "Prep")
    graph.add_transition("Prep", "Cook")
    graph.add_transition("Cook", "Serve")

    assert graph.successors("Gather") == ["Prep"]
    assert graph.predecessors("Cook") == ["Prep"]
    assert graph.successors("Cook") == ["Serve"]
    assert sorted(graph.steps) == ["Cook", "Gather", "Prep", "Serve"]


def test_remove_step_drops_incoming_and_outgoing_edges() -> None:
    graph = ProcessGraph("cleanup")
    graph.add_transition("Start", "Middle")
    graph.add_transition("Middle", "End")
    graph.add_transition("Extra", "Middle")

    graph.remove_step("Middle")

    assert "Middle" not in graph.steps
    assert graph.successors("Start") == []
    assert graph.predecessors("End") == []
    assert graph.predecessors("Middle") == []


def test_update_step_keeps_edges_intact() -> None:
    graph = ProcessGraph("rename")
    graph.add_transition("Prep", "Cook")
    graph.add_transition("Cook", "Plate")
    graph.add_transition("Cleanup", "Cook")

    graph.update_step("Cook", "Saute")

    assert "Cook" not in graph.steps
    assert "Saute" in graph.steps
    assert graph.successors("Saute") == ["Plate"]
    assert graph.predecessors("Saute") == ["Cleanup", "Prep"]
    assert graph.predecessors("Plate") == ["Saute"]


def test_steps_property_returns_live_view() -> None:
    graph = ProcessGraph("live-view")
    graph.add_step("Initial")

    steps_view = graph.steps
    assert "Initial" in steps_view

    graph.add_step("Later")
    assert "Later" in steps_view

    graph.remove_step("Initial")
    assert "Initial" not in steps_view
