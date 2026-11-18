"""Smoke test: read frames from every configured camera for 2 s each.

Per §1.4 rule 3: env var must be set before import cv2. Reads URL from config (F1).
"""

import os
from pathlib import Path

os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"  # per §1.4 rule 3

import time

import cv2

from core.config import load

ROOT = Path(__file__).resolve().parent.parent


def read_one(cam: str, url: str, seconds: float = 2.0) -> str:
    cap = cv2.VideoCapture(
        url,
        cv2.CAP_FFMPEG,
        [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000, cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000],
    )
    if not cap.isOpened():
        return "OPEN FAILED"
    n, last_shape = 0, None
    t0 = time.time()
    while time.time() - t0 < seconds:
        ok, frame = cap.read()
        if ok and frame is not None:
            n += 1
            last_shape = frame.shape  # per-camera shape, never stale (F5 fix)
    cap.release()
    if n == 0:
        return "no frames"  # never reference an unassigned `frame` (F5 fix)
    return f"{n} frames in {seconds}s (~{n / seconds:.1f} fps), shape={last_shape}"


def main() -> None:
    cfg = load(str(ROOT / "config" / "config.yaml"))
    for cam in cfg["cameras"]:
        url = f"rtsp://{cfg['rtsp_host']}:{cfg['rtsp_port']}/{cfg['rtsp_path'].format(cam=cam)}"
        print(f"{cam}: {read_one(cam, url)}")


if __name__ == "__main__":
    main()
