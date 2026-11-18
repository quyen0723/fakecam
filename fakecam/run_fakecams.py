"""Publish each configured fake camera as a live RTSP stream, auto-restart on exit.

Per CODE_STANDARD §1: URLs and camera list come from config only.
Per §7: fixed argv for ffmpeg (no shell interpolation); filenames validated; no traversal.
Week-1 pass criterion "kill one ffmpeg and it comes back" is served by the built-in
watchdog until services/supervisor.py lands (playbook §3.4).
"""

import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

from core.config import load

ROOT = Path(__file__).resolve().parent.parent
PID_FILE = ROOT / "data" / "fakecam.pids"
NAME_RE = re.compile(r"^[a-zA-Z0-9_-]+\.mp4$")


def safe_video(cam: str) -> Path:
    """Resolve videos/<cam>.mp4 strictly inside videos/ per §7 (no traversal)."""
    name = f"{cam}.mp4"
    if not NAME_RE.match(name):
        raise ValueError(f"invalid video filename {name!r}")
    p = (ROOT / "videos" / name).resolve()
    if ROOT.joinpath("videos").resolve() not in p.parents:
        raise ValueError(f"video escapes videos/: {p}")
    return p


def rtsp_url(cam: str, cfg: dict) -> str:
    """Build the publish URL from config only — no hardcoded host/port (F1 fix)."""
    return f"rtsp://{cfg['rtsp_host']}:{cfg['rtsp_port']}/{cfg['rtsp_path'].format(cam=cam)}"


def publisher_cmd(cam: str, video: Path, cfg: dict) -> list[str]:
    """Fixed argv publisher."""
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
        rtsp_url(cam, cfg),
    ]


def owns_pid(pid: int) -> bool:
    """Only kill a PID that really is one of our ffmpeg publishers (F3: PID reuse).

    Cross-platform via psutil — works on macOS/Linux/Windows alike. If psutil is
    unavailable, fail CLOSED (return False): never kill an unverified process.
    """
    try:
        import psutil
    except ImportError:  # pragma: no cover — deps installed via pyproject
        print("psutil missing: refusing to kill unverified pids", file=sys.stderr)
        return False
    try:
        return "ffmpeg" in psutil.Process(pid).name().lower()
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return False


def stop_running() -> None:
    if PID_FILE.exists():
        for pid in [int(x) for x in PID_FILE.read_text().split()]:
            try:
                if owns_pid(pid):
                    os.kill(pid, signal.SIGTERM)
                else:
                    print(f"skip pid {pid}: not an ffmpeg process", file=sys.stderr)
            except ProcessLookupError:
                pass
        PID_FILE.unlink()


def spawn(cam: str, cfg: dict) -> subprocess.Popen:
    return subprocess.Popen(publisher_cmd(cam, safe_video(cam), cfg))


def start(cfg: dict) -> None:
    """Launch all publishers + watchdog. Blocks; Ctrl+C stops children cleanly."""
    stop_running()
    PID_FILE.parent.mkdir(exist_ok=True)
    procs = {cam: spawn(cam, cfg) for cam in cfg["cameras"]}
    PID_FILE.write_text(" ".join(str(p.pid) for p in procs.values()))
    print("publishers:", {c: p.pid for c, p in procs.items()})

    backoff = {c: 1.0 for c in procs}
    max_backoff = 60.0
    while True:
        try:
            time.sleep(2)
            for cam, p in procs.items():
                if p.poll() is None:
                    continue
                print(
                    f"{cam}: exited rc={p.returncode}, restart in {backoff[cam]}s", file=sys.stderr
                )
                time.sleep(backoff[cam])
                backoff[cam] = min(backoff[cam] * 2, max_backoff)
                procs[cam] = spawn(cam, cfg)  # supervised later per §3.4
                PID_FILE.write_text(" ".join(str(p.pid) for p in procs.values()))
                print(f"{cam}: pid {procs[cam].pid}")
        except KeyboardInterrupt:
            stop_running()
            return


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "stop":
        stop_running()
        return
    start(load(str(ROOT / "config" / "config.yaml")))


if __name__ == "__main__":
    main()
