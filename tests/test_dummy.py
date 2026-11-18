"""DummyPilot interval logic (pure) — per-camera state, 35 s outside cooldown grid."""

import time
from types import SimpleNamespace

from core.contract import FrameMeta
from pilots.dummy import DummyPilot

F = SimpleNamespace(shape=(720, 1280, 3))


def meta(cam="cam01"):
    return FrameMeta(camera_id=cam, frame_id=1, ts_frame=time.time())


def test_first_frame_emits_per_camera():
    d = DummyPilot()
    d.setup({})
    assert d.on_frame(F, meta("cam01")) and d.on_frame(F, meta("cam02"))


def test_second_alert_within_interval_is_swallowed():
    d = DummyPilot()
    d.setup({})
    assert d.on_frame(F, meta("cam01"))
    d._last["cam01"] = time.time()  # pretend just emitted
    assert d.on_frame(F, meta()) == []


def test_interval_is_35s_not_30s():
    from pilots.dummy import INTERVAL_S

    assert INTERVAL_S == 35.0  # plan-review decision 19/11 — guard against "fix" to 30
