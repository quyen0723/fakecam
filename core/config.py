"""Load and validate config.yaml — the only place that reads it. Per §1.4 rule 1."""

import re
from pathlib import Path
from typing import Any

import yaml

CAMERA_ID_RE = re.compile(r"^cam[0-9]{2}$")


def load(path: str = "config/config.yaml") -> dict[str, Any]:
    cfg = yaml.safe_load(Path(path).read_text())
    cams = cfg["cameras"]
    if not cams:
        raise ValueError("cameras must not be empty")
    for cam in cams:
        if not CAMERA_ID_RE.match(cam):
            raise ValueError(f"camera_id {cam!r} does not match ^cam[0-9]{2}$")
    return cfg
