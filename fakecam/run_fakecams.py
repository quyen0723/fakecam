"""Publish each configured fake camera as a live RTSP stream.

Per CODE_STANDARD §1: URLs and camera list come from config only.
Per §7: fixed argv for ffmpeg (no shell interpolation); filenames validated;
no path traversal.
"""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from core.config import load

ROOT = Path(__file__).resolve().parent.parent
PID_FILE = ROOT / "data" / "fakecam.pids"
RTSP_HOST = "127.0.0.1"  # per §7: loopback unless explicitly opened (requires PR note)

NAME_RE = __import__("re").compile(r"^[a-zA-Z0-9_-]+\.mp4$")


def safe_video(cam: str) -> Path:
    """Resolve videos/<cam>.mp4 strictly inside videos/ per §7 (no traversal)."""
    name = f"{cam}.mp4"
    if not NAME_RE.match(name):
        raise ValueError(f"invalid video filename {name!r}")
    p = (ROOT / "videos" / name).resolve()
    if ROOT.joinpath("videos").resolve() not in p.parents:
        raise ValueError(f"video escapes videos/: {p}")
    return p


def publisher_cmd(cam: str, video: Path, rtsp_path: str) -> list[str]:
    """Fixed argv publisher. Layout: rtsp://<host>:8554/<rtsp_path>.format(cam=cam)."""
    return [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-re",
        "-stream_loop",
        "-1",
        "-i",
        str(video),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-tune",
        "zerolatency",
        "-g",
        "15",
        "-an",
        "-f",
        "rtsp",
        "-rtsp_transport",
        "tcp",
        f"rtsp://{RTSP_HOST}:8554/{rtsp_path.format(cam=cam)}",
    ]


def stop_running() -> None:
    if PID_FILE.exists():
        for pid in [int(x) for x in PID_FILE.read_text().split()]:
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        PID_FILE.unlink()


def start(cameras: list[str], rtsp_path: str) -> None:
    stop_running()
    PID_FILE.parent.mkdir(exist_ok=True)
    procs = {}
    for cam in cameras:
        cmd = publisher_cmd(cam, safe_video(cam), rtsp_path)
        procs[cam] = subprocess.Popen(cmd)  # supervised later per §3.4
        print(f"{cam}: pid {procs[cam].pid}")
    PID_FILE.write_text(" ".join(str(p.pid) for p in procs.values()))
    time.sleep(2)  # let MediaMTX accept ANNOUNCE; failures surface below
    for cam, p in procs.items():
        if p.poll() is not None:
            print(f"{cam}: publisher exited rc={p.returncode}", file=sys.stderr)
            raise SystemExit(2)


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "stop":
        stop_running()
        return
    cfg = load(str(ROOT / "config" / "config.yaml"))
    start(cfg["cameras"], cfg["rtsp_path"])


if __name__ == "__main__":
    main()
