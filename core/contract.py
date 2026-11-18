"""Pilot contract — the only interface pilot teams implement (playbook §1.2).

Frozen dataclasses for immutable payloads; Protocol for the structural contract.
Per §1.4: no module other than this one defines alert/camera payload shapes.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

import numpy as np


@dataclass(frozen=True)
class FrameMeta:
    """Metadata of one frame delivered to a pilot."""

    camera_id: str
    frame_id: int  # increasing per camera
    ts_frame: float  # time.time() when the reader received the frame


@dataclass
class AlertDraft:
    """What a pilot wants the platform to record. Platform adds ts_alert (§3.3)."""

    event_type: str  # fire | smoke | intrusion | dwell
    confidence: float
    bbox: Sequence[int] | None = None
    model_version: str = ""


class Pilot(Protocol):
    """Structural interface: pilot teams only implement setup + on_frame.

    No RTSP, no files, no clip handling in pilot code — per playbook §1.2.
    """

    name: str

    def setup(self, cfg: dict) -> None: ...

    def on_frame(self, frame: np.ndarray, meta: FrameMeta) -> list[AlertDraft]: ...
