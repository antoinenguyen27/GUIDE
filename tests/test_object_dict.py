from __future__ import annotations

import pytest

from gemini.object_dict import ObjectDict


@pytest.fixture()
def object_dict(home_layout: dict) -> ObjectDict:
    return ObjectDict(home_layout)


def test_add_and_find_object(object_dict: ObjectDict) -> None:
    prep_path = ("Kitchen", "Benches", "Island", "Zones", "Prep")
    assert object_dict.add_object(prep_path, "thermometer")
    assert "thermometer" in object_dict.get_path(prep_path)
    assert object_dict.find_object("thermometer") == prep_path


def test_move_object_updates_both_locations(object_dict: ObjectDict) -> None:
    new_home = ("Kitchen", "Cabinets", "Upper_Left")
    assert object_dict.move_object("dish_soap", new_home)
    assert "dish_soap" in object_dict.get_path(new_home)
    original_path = ("Kitchen", "Benches", "Wall", "Zones", "Left_of_Sink")
    assert "dish_soap" not in object_dict.get_path(original_path, default=[])


def test_remove_object_prunes_empty_branches(object_dict: ObjectDict) -> None:
    guest_surface = ("Office", "Desks", "Guest", "Surface", "Center")
    assert object_dict.remove_object("charging_station", guest_surface)
    assert not object_dict.has_path(guest_surface)
    assert not object_dict.has_path(guest_surface[:-1])


def test_extend_objects_respects_deduplication(object_dict: ObjectDict) -> None:
    drawer_path = ("Kitchen", "Drawers", "Top")
    added = object_dict.extend_objects(drawer_path, ["chopsticks", "spoons"])
    assert added == 1
    contents = object_dict.get_path(drawer_path)
    assert contents.count("spoons") == 1


def test_as_dict_returns_copy(object_dict: ObjectDict) -> None:
    snapshot = object_dict.as_dict()
    snapshot["Kitchen"]["Drawers"]["Top"].append("peeler")
    assert "peeler" not in object_dict.get_path(("Kitchen", "Drawers", "Top"))
