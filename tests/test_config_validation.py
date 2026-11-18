"""Validation tests for core.config.load — invalid config must exit loudly (§1.4 rule 1)."""

import pytest
import yaml

from core.config import load

BASE = {
    "rtsp_host": "127.0.0.1",
    "rtsp_port": 8554,
    "hls_port": 8888,
    "rtmp_port": 1935,
    "webrtc_port": 8889,
    "rtsp_path": "live/{cam}",
    "cameras": ["cam01"],
    "pre": 10,
    "post": 10,
    "seg_s": 2,
    "keep_s": 600,
    "cooldown_s": 30,
}


def write(tmp_path, cfg):
    p = tmp_path / "c.yaml"
    p.write_text(yaml.safe_dump(cfg))
    return str(p)


def test_valid_minimal_config_loads(tmp_path):
    cfg = load(write(tmp_path, BASE))
    assert cfg["rtsp_port"] == 8554


@pytest.mark.parametrize(
    "key,val",
    [
        ("pre", 0),
        ("post", -1),
        ("seg_s", "2"),
        ("keep_s", True),
        ("cooldown_s", 0),
    ],
)
def test_non_positive_int_rejected(tmp_path, key, val):
    bad = dict(BASE)
    bad[key] = val
    with pytest.raises(ValueError, match=key or "positive"):
        load(write(tmp_path, bad))


def test_bad_port(tmp_path):
    bad = dict(BASE)
    bad["rtsp_port"] = 99999
    with pytest.raises(ValueError, match="rtsp_port"):
        load(write(tmp_path, bad))


def test_bad_path_placeholder(tmp_path):
    bad = dict(BASE)
    bad["rtsp_path"] = "live/static"
    with pytest.raises(ValueError, match="rtsp_path"):
        load(write(tmp_path, bad))


@pytest.mark.parametrize("cams", [[], ["camera01"], ["cam1"], ["CAM01"]])
def test_bad_cameras_rejected(tmp_path, cams):
    bad = dict(BASE)
    bad["cameras"] = cams
    with pytest.raises(ValueError):
        load(write(tmp_path, bad))


def test_mediamtx_render_lists_every_camera():
    from scripts.gen_mediamtx import render

    out = render(dict(BASE))
    assert "live/cam01:" in out and "# GENERATED" in out
    assert "hlsAddress: 127.0.0.1:8888" in out  # rendered from config, not hardcoded
    assert "rtspAddress: 127.0.0.1:8554" in out
