"""Alert emit: atomic JSON write + platform-side dedup grid (playbook §3.3, updated 18/11).

Pilots call nothing themselves — run_pilot calls emit_alert per AlertDraft.
Returns the written alert dict, or None when the dedup grid swallows it (info for
run_pilot latency accounting).
"""

import json
import os
import time
from pathlib import Path
from typing import Any

_last: dict[tuple, float] = {}  # (event_type, camera_id) -> ts of last accepted alert


def emit_alert(
    d: Any, meta: Any, pilot_name: str, root: str = "data/alerts", cooldown_s: int = 30
) -> dict[str, Any] | None:
    """Write AlertDraft to disk atomically. None if within cooldown window."""
    now = time.time()
    key = (d.event_type, meta.camera_id)
    if now - _last.get(key, 0.0) < cooldown_s:
        return None
    _last[key] = now
    a = {
        "alert_id": f"{meta.camera_id}_{int(now * 1000)}_{d.event_type}",
        "camera_id": meta.camera_id,
        "pilot": pilot_name,
        "event_type": d.event_type,
        "frame_id": meta.frame_id,
        "ts_frame": meta.ts_frame,
        "ts_alert": now,
        "confidence": d.confidence,
        "bbox": list(d.bbox) if d.bbox else None,
        "model_version": d.model_version,
    }
    p = Path(root) / meta.camera_id / f"{a['alert_id']}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(a))
    os.replace(tmp, p)  # atomic; Windows-safe since 3.3 (playbook risk: Windows file locks)
    return a
