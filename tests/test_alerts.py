"""Pure-logic tests for alerts + latency (no RTSP, no files outside tmp)."""

import json
import time
from types import SimpleNamespace

from core.alerts import _last, emit_alert
from core.contract import FrameMeta
from core.latency import LatRecorder


def _draft(etype="fire", conf=0.9):
    return SimpleNamespace(event_type=etype, confidence=conf, bbox=[1, 2, 3, 4], model_version="v1")


def _meta(cam="cam01", fid=1):
    return FrameMeta(camera_id=cam, frame_id=fid, ts_frame=time.time() - 0.5)


def test_emit_writes_valid_json(tmp_path):
    _last.clear()
    a = emit_alert(_draft(), _meta(), "dummy", root=str(tmp_path))
    assert a is not None
    data = json.loads((tmp_path / "cam01" / f"{a['alert_id']}.json").read_text())
    assert data["camera_id"] == "cam01" and data["pilot"] == "dummy"
    assert data["event_type"] == "fire" and data["bbox"] == [1, 2, 3, 4]


def test_dedup_grid_blocks_within_cooldown(tmp_path):
    _last.clear()
    d = _draft()
    first = emit_alert(d, _meta(), "dummy", root=str(tmp_path), cooldown_s=30)
    second = emit_alert(d, _meta(fid=2), "dummy", root=str(tmp_path), cooldown_s=30)
    assert first is not None and second is None  # grid swallows within 30 s


def test_dedup_key_includes_event_type_and_camera(tmp_path):
    _last.clear()
    emit_alert(_draft(), _meta("cam01"), "dummy", root=str(tmp_path))
    smoke = SimpleNamespace(event_type="smoke", confidence=0.5, bbox=None, model_version="v1")
    a2 = emit_alert(_draft(), _meta("cam02"), "dummy", root=str(tmp_path))
    a3 = emit_alert(smoke, _meta("cam01"), "dummy", root=str(tmp_path))
    assert a2 is not None and a3 is not None  # different camera/type pass the grid


def test_latency_flushes_with_header(tmp_path):
    rec = LatRecorder(out=str(tmp_path / "lat.csv"), flush_s=999)
    rec.add("cam01", 0.123)
    rec.add("cam02", 0.456)
    rec.flush()
    rows = (tmp_path / "lat.csv").read_text().strip().splitlines()
    assert rows[0] == "camera,ts,lat_s" and len(rows) == 3
