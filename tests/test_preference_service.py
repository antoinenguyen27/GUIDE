from __future__ import annotations

import pytest

from gemini.preference_service import PreferenceService


@pytest.fixture()
def preference_service(home_layout: dict) -> PreferenceService:
    return PreferenceService(initial_object_locations=home_layout)


def test_toolkit_is_callable(preference_service: PreferenceService) -> None:
    toolkit = preference_service.toolkit
    assert len(toolkit) >= 5
    assert all(callable(tool) for tool in toolkit)
    declarations = preference_service.function_declarations
    assert len(declarations) == len(toolkit)
    assert {decl["name"] for decl in declarations} >= {
        "list_process_graphs",
        "create_process_graph",
        "add_object",
    }


def test_lookup_tool_matches_declarations(preference_service: PreferenceService) -> None:
    toolkit = preference_service.toolkit
    declarations = preference_service.function_declarations
    first_name = declarations[0]["name"]
    resolved = preference_service.get_tool_callable(first_name)
    assert callable(resolved)
    assert resolved.__func__ is toolkit[0].__func__
    assert resolved.__self__ is toolkit[0].__self__


def test_process_graph_crud(preference_service: PreferenceService) -> None:
    create = preference_service.tool_create_process_graph("kitchen-reset")
    assert create["status"] == "success"

    preference_service.tool_add_process_step("kitchen-reset", "Clear benches")
    preference_service.tool_add_process_transition("kitchen-reset", "Clear benches", "Wipe benches")

    listing = preference_service.tool_list_process_graphs()
    assert listing["status"] == "success"
    graph = next(item for item in listing["graphs"] if item["name"] == "kitchen-reset")
    assert "Clear benches" in graph["steps"]
    assert {"from": "Clear benches", "to": "Wipe benches"} in graph["transitions"]

    delete = preference_service.tool_delete_process_graph("kitchen-reset")
    assert delete["status"] == "success"
    missing = preference_service.tool_delete_process_graph("kitchen-reset")
    assert missing["status"] == "error"


def test_object_tools(preference_service: PreferenceService) -> None:
    add = preference_service.tool_add_object(
        ["Kitchen", "Fridge", "Door"], "butter", allow_duplicates=False
    )
    assert add["status"] == "success"

    move = preference_service.tool_move_object(
        "dish_soap", ["Kitchen", "Benches", "Wall", "Zones", "Right_of_Sink"]
    )
    assert move["status"] == "success"

    lookup = preference_service.tool_list_object_locations("dish_soap")
    assert lookup["status"] == "success"
    assert lookup["locations"] == [["Kitchen", "Benches", "Wall", "Zones", "Right_of_Sink"]]


def test_delete_path(preference_service: PreferenceService) -> None:
    result = preference_service.tool_delete_path(
        ["Kitchen", "Benches", "Wall", "Zones", "Right_of_Sink"]
    )
    assert result["status"] == "success"
    repeat = preference_service.tool_delete_path(
        ["Kitchen", "Benches", "Wall", "Zones", "Right_of_Sink"]
    )
    assert repeat["status"] == "error"
