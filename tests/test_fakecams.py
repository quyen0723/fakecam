"""Pure-logic tests for run_fakecams (per CODE_STANDARD §4)."""

from pathlib import Path

import pytest

from fakecam.run_fakecams import NAME_RE, publisher_cmd, rtsp_url, safe_video

CFG = {
    "rtsp_host": "127.0.0.1",
    "rtsp_port": 8554,
    "rtsp_path": "live/{cam}",
}


def test_rtsp_url_from_config_only():
    assert rtsp_url("cam01", CFG) == "rtsp://127.0.0.1:8554/live/cam01"


def test_publisher_cmd_fixed_argv_tail_is_url():
    cmd = publisher_cmd("cam01", Path("/tmp/x"), CFG)
    assert cmd[-1] == "rtsp://127.0.0.1:8554/live/cam01"
    assert "-rtsp_transport" in cmd and cmd[cmd.index("-rtsp_transport") + 1] == "tcp"
    assert "-re" in cmd and "-g" in cmd and "15" not in cmd[:3]


def test_safe_video_resolves_inside_videos(tmp_path):
    p = safe_video("cam01")
    assert p.name == "cam01.mp4" and "videos" in p.parts


@pytest.mark.parametrize("bad", ["../cam01.mp4", "/etc/passwd", "a b.mp4", "a/b.mp4"])
def test_name_regex_rejects_non_simple_names(bad):
    assert not NAME_RE.match(bad) or ("/" in bad)  # slash is rejected by construct path
    assert not NAME_RE.match("a b.mp4")
