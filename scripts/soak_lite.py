"""Soak-lite: monitor the 4-camera stack; CSV per poll; verdict at end (to-do 1.1).

Pass criterion (playbook week 1): 4 cameras run >= 1 h, kill one ffmpeg and it comes
back (already live-verified 19/11). This script records continuity evidence.

Usage: .venv/bin/python -m scripts.soak_lite [minutes]
"""

import csv
import sys
import time
import urllib.request
from pathlib import Path

import psutil

from core.config import load

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "metrics" / "soak_lite.csv"
OUT = OUT.with_name("soak_lite_" + time.strftime("%Y%m%d_%H%M%S") + ".csv")


def ffmpeg_count() -> int:
    """Count LIVE ffmpeg publishers — zombies (dead publishers awaiting reap) excluded.

    Zombie ffmpeg still carries the name but is not publishing (found 19/11: count 10)."""
    n = 0
    for p in psutil.process_iter(["name"]):
        try:
            if "ffmpeg" in (p.info["name"] or "").lower() and p.cmdline():
                n += 1
        except (psutil.ZombieProcess, psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return n


def hls_ok(cfg: dict) -> int:
    ok = 0
    for cam in cfg["cameras"]:
        url = (
            f"http://{cfg['rtsp_host']}:{cfg['hls_port']}"
            f"/{cfg['rtsp_path'].format(cam=cam)}/index.m3u8"
        )
        try:
            with urllib.request.urlopen(url, timeout=3) as r:
                ok += r.status == 200
        except OSError:
            pass  # transient HLS error counts as a miss for this poll
    return ok


def main() -> None:
    try:
        minutes = float(sys.argv[1]) if len(sys.argv) > 1 else 60.0
    except ValueError as e:
        raise SystemExit(f"minutes must be a number: {e}")
    if minutes <= 0:
        raise SystemExit(f"minutes must be > 0, got {minutes}")
    cfg = load(str(ROOT / "config" / "config.yaml"))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    end = time.time() + minutes * 60
    polls, bad = 0, 0
    with open(OUT, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ts", "ffmpeg_count", "hls_ok"])
        while time.time() < end:
            try:
                n, h = ffmpeg_count(), hls_ok(cfg)
            except Exception as e:  # noqa: BLE001 — monitor must SURVIVE, evidence first
                w.writerow([f"{time.time():.0f}", "ERR", repr(e)[:120]])
                f.flush()
                bad += 1  # a crashed poll counts as an anomaly — never silently skipped
                polls += 1
                time.sleep(30)
                continue
            w.writerow([f"{time.time():.0f}", n, h])
            f.flush()
            if n < 4 or h < 4:
                bad += 1
            polls += 1
            time.sleep(30)
    # Poll-level report: anomalies = polls where any camera was missing/below spec
    uptime = 100 * (polls - bad) / max(polls, 1)
    verdict = "PASS" if bad == 0 else ("PASS-WITH-GAPS" if uptime >= 95 else "FAIL")
    print(
        f"soak {minutes:.0f} min: {polls} polls, {bad} anomalies, uptime {uptime:.1f}% → {verdict}"
    )


if __name__ == "__main__":
    main()
