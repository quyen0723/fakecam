"""DummyPilot: emits one synthetic alert per camera every 35 s — no model needed.

35 s (not 30 s) keeps DummyPilot outside the platform dedup grid (30 s, §3.3),
which was a plan-review decision 19/11 — do not "fix" it back to 30 s.
Enables end-to-end platform tests without pilot teams (playbook §1.3).
"""

import time

from core.contract import AlertDraft, FrameMeta

INTERVAL_S = 35.0


class DummyPilot:
    name = "dummy"

    def __init__(self) -> None:
        self._last: dict[str, float] = {}

    def setup(self, cfg: dict) -> None:
        self.cfg = cfg

    def on_frame(self, frame, meta: FrameMeta) -> list[AlertDraft]:
        now = time.time()
        if now - self._last.get(meta.camera_id, 0.0) < INTERVAL_S:
            return []
        self._last[meta.camera_id] = now  # per-camera state (§1.2 rule 1)
        return [AlertDraft(event_type="dummy", confidence=1.0, bbox=None, model_version="dummy-v1")]
