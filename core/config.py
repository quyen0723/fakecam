"""Load and validate config.yaml — the only place that reads it.

Per §1.4 rule 1: validation runs at startup, invalid values exit immediately.
"""

import re
from pathlib import Path
from typing import Any

import yaml

CAMERA_ID_RE = re.compile(r"^cam[0-9]{2}$")
POSITIVE_INT_KEYS = ("pre", "post", "seg_s", "keep_s", "cooldown_s")


def load(path: str = "config/config.yaml") -> dict[str, Any]:
    cfg = yaml.safe_load(Path(path).read_text())

    cameras = cfg.get("cameras")
    if not isinstance(cameras, list) or not cameras:
        raise ValueError("cameras must be a non-empty list")
    for cam in cameras:
        if not isinstance(cam, str) or not CAMERA_ID_RE.match(cam):
            raise ValueError(f"camera_id {cam!r} does not match ^cam[0-9]{{2}}$")

    for key in POSITIVE_INT_KEYS:
        value = cfg.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise ValueError(f"{key} must be a positive integer, got {value!r}")

    host = cfg.get("rtsp_host")
    if not isinstance(host, str) or not host:
        raise ValueError("rtsp_host must be a non-empty string")
    for key in ("rtsp_port", "hls_port", "rtmp_port", "webrtc_port"):
        port = cfg.get(key)
        if not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= 65535:
            raise ValueError(f"{key} must be 1-65535, got {port!r}")

    rtsp_path = cfg.get("rtsp_path")
    if not isinstance(rtsp_path, str) or "{cam}" not in rtsp_path:
        raise ValueError(f"rtsp_path must contain the {{cam}} placeholder, got {rtsp_path!r}")

    return cfg
