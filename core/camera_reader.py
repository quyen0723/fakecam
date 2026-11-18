"""RTSP reader: latest-frame only, background thread, backoff reconnect (§3.1).

Semantics fixed by playbook: no frame queues (anti frame-accumulation, risk table);
reconnect logged on FIRST FRAME, not on connect (logged 18/11 caveat).
Must NOT keep frames in lists (risk table: OpenCV memory leak).
"""

import csv
import threading
import time
from pathlib import Path

from core.contract import FrameMeta


class CameraReader:
    """Expose only the newest frame via read(); one background thread per camera."""

    def __init__(
        self,
        camera_id: str,
        url: str,
        log_dir: str = "data/logs",
        stall_s: float = 5.0,
        max_backoff: float = 10.0,
    ):
        self.id, self.url = camera_id, url
        self.stall_s, self.max_backoff = stall_s, max_backoff
        self._cv = threading.Condition()
        self._frame = None
        self._meta: FrameMeta | None = None
        self._fid = 0
        self._stop = threading.Event()
        self._log = Path(log_dir) / "reconnect.csv"
        self._log.parent.mkdir(parents=True, exist_ok=True)
        self._t = threading.Thread(target=self._run, daemon=True)

    def start(self) -> "CameraReader":
        self._t.start()
        return self

    def stop(self) -> None:
        self._stop.set()

    def read(self, after_id: int = -1, timeout: float = 1.0):
        """Return (frame, meta) with frame_id > after_id, or None on timeout."""
        with self._cv:
            # _fid starts at 0 → `_fid > -1` is TRUE before any frame arrives;
            # guard on _meta (bug found live 19/11: read() returned (None, None) and crashed)
            self._cv.wait_for(lambda: self._meta is not None and self._fid > after_id, timeout)
            if self._meta is None or self._fid <= after_id:
                return None
            return self._frame, self._meta

    def _open(self):
        import os  # env must exist before import cv2 (§1.4 rule 3) — see run_pilot

        import cv2

        os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")
        return cv2.VideoCapture(
            self.url,
            cv2.CAP_FFMPEG,
            [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000, cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000],
        )

    def _log_event(self, at: float, now: float, why: str) -> None:
        with open(self._log, "a", newline="") as f:
            csv.writer(f).writerow([self.id, f"{at:.3f}", f"{now:.3f}", f"{now - at:.1f}", why])

    def _run(self) -> None:
        backoff, lost_at = 1.0, None
        cap = None
        while not self._stop.is_set():
            if cap is None:
                cap = self._open()
                if not cap.isOpened():
                    cap.release()
                    cap = None
                    lost_at = lost_at or time.time()
                    time.sleep(backoff)
                    backoff = min(backoff * 2, self.max_backoff)
                    continue
                got_first, last_ok = False, time.time()
            ok, frame = cap.read()
            now = time.time()
            if not ok or frame is None:
                if now - last_ok > self.stall_s:  # lost or stalled stream
                    lost_at = lost_at or last_ok
                    cap.release()
                    cap = None  # force reopen (backoff applies next loop)
                    time.sleep(backoff)
                    backoff = min(backoff * 2, self.max_backoff)
                    continue
                time.sleep(0.05)
                continue
            if not got_first:
                got_first = True
                if lost_at is not None:  # first frame, not "connected" (18/11 caveat)
                    self._log_event(lost_at, now, "first_frame")
                    lost_at = None
                backoff = 1.0
            last_ok = now
            with self._cv:  # latest frame only — no queues (risk table)
                self._fid += 1
                self._frame = frame
                self._meta = FrameMeta(self.id, self._fid, now)
                self._cv.notify_all()
        if cap is not None:
            cap.release()
