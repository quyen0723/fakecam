"""Latency recorder — per-frame timing, flushed to CSV every few seconds (§3.3)."""

import csv
import time
from pathlib import Path


class LatRecorder:
    """In-memory buffer of (camera, ts, lat_s), flushed to CSV every flush_s seconds."""

    def __init__(self, out: str = "data/metrics/frame_latency.csv", flush_s: float = 5.0):
        self.path = Path(out)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.flush_s = flush_s
        self._buf: list[list] = []
        self._last_flush = 0.0

    def add(self, cam: str, lat_s: float) -> None:
        self._buf.append([cam, f"{time.time():.3f}", f"{lat_s:.4f}"])

    def maybe_flush(self) -> None:
        now = time.time()
        if self._buf and now - self._last_flush >= self.flush_s:
            self.flush()

    def flush(self) -> None:
        self._last_flush = time.time()
        if not self.path.exists():
            self.path.write_text("camera,ts,lat_s\n")  # header on first use
        with open(self.path, "a", newline="") as f:
            csv.writer(f).writerows(self._buf)
        self._buf.clear()
