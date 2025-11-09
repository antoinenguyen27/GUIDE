"""Default object location map shared across runtime and tests."""

from __future__ import annotations

DEFAULT_HOME_LAYOUT = {
    "Kitchen": {
        "Benches": {
            "Island": {
                "Zones": {
                    "Prep": ["knife_block", "paper_towels"],
                    "Appliance": ["toaster"],
                }
            },
            "Wall": {
                "Zones": {
                    "Left_of_Sink": ["dish_soap"],
                    "Right_of_Sink": [],
                }
            },
        },
        "Drawers": {
            "Top": ["knives", "spoons", "forks"],
            "Middle": ["tongs", "ladle"],
        },
        "Cabinets": {
            "Upper_Left": ["mugs", "coffee_filters"],
        },
        "Fridge": {
            "Crisper": ["apples"],
            "Door": ["milk"],
        },
    },
    "Office": {
        "Desks": {
            "Antoine": {
                "Surface": {
                    "Left": ["lamp"],
                    "Center": ["laptop_stand"],
                },
                "Drawers": {
                    "Left": ["notebook"],
                    "Right": ["stapler"],
                },
            },
            "Guest": {
                "Surface": {"Center": ["charging_station"]},
                "Drawers": {},
            },
        }
    },
}
