from __future__ import annotations

import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROOT_STR = str(ROOT)
if ROOT_STR not in sys.path:
    sys.path.insert(0, ROOT_STR)

import pytest

from gemini.home_layout import DEFAULT_HOME_LAYOUT

@pytest.fixture()
def home_layout() -> dict:
    """Return a fresh copy of the canonical home layout."""
    return deepcopy(DEFAULT_HOME_LAYOUT)
