"""load_pilot duck-typing: any class with setup/on_frame is discoverable (I1)."""

import sys
import types

import pytest

from core.run_pilot import load_pilot


class FakePilot:
    name = "fake"

    def setup(self, cfg):
        self.cfg = cfg

    def on_frame(self, frame, meta):
        return []


def test_discovers_arbitrary_class_name():
    mod = types.ModuleType("pilots.fake")
    mod.FirePilotZ = FakePilot  # team chose the name — loader must still find it
    sys.modules["pilots.fake"] = mod
    p = load_pilot("fake")
    assert p.name == "fake" and callable(p.on_frame)


def test_missing_pilot_module_fails_loud():
    # importlib raises ModuleNotFoundError — assert precisely, not blind Exception
    with pytest.raises(ModuleNotFoundError):
        load_pilot("no_such_pilot")
