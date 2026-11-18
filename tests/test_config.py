"""Config loader tests (pure logic per CODE_STANDARD §4)."""

import pytest

from core.config import CAMERA_ID_RE, load


def test_default_config_loads():
    cfg = load()
    assert cfg["cameras"] == ["cam01", "cam02", "cam03", "cam04"]
    assert cfg["pre"] == 10 and cfg["post"] == 10


@pytest.mark.parametrize("bad", ["CAM01", "c1", "camera001", "cam01x"])
def test_bad_camera_id_rejected(bad):
    assert not CAMERA_ID_RE.match(bad)


@pytest.mark.parametrize("good", ["cam01", "cam99"])
def test_good_camera_id(good):
    assert CAMERA_ID_RE.match(good)
