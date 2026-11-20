"""Run one pilot worker: python -m core.run_pilot --pilot dummy [--cams cam01,cam02].

Per §3.3: reader per pilot worker (no frame passing between processes);
URL/built from config only; latency = on_frame return − ts_frame.
Env var stays here so cv2 is imported AFTER it is set (§1.4 rule 3).
"""

import os

os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"  # per §1.4 rule 3

import argparse
import time
from pathlib import Path

from core.alerts import emit_alert
from core.camera_reader import CameraReader
from core.config import load
from core.latency import LatRecorder

ROOT = Path(__file__).resolve().parent.parent


def load_pilot(name: str):
    """Import pilots.<name>; the pilot class is found by capability, not name.

    Report §2 asked teams to name classes themselves (e.g. FirePilot) — so we duck-type:
    first class in the module with setup() + on_frame() wins. Keeps the contract open.
    """
    import importlib
    import inspect

    if name == "dummy":
        from pilots.dummy import DummyPilot

        return DummyPilot()
    mod = importlib.import_module(f"pilots.{name}")
    for _, obj in inspect.getmembers(mod, inspect.isclass):
        # capability-based only: contract types (AlertDraft/FrameMeta) lack on_frame,
        # so nothing else can qualify — no module-identity guard needed (test I1).
        if not obj.__name__.startswith("_") and all(hasattr(obj, m) for m in ("setup", "on_frame")):
            return obj()
    raise ValueError(f"no pilot class with setup/on_frame in pilots.{name}")


def main() -> None:
    ap = argparse.ArgumentParser(description="run one pilot worker")
    ap.add_argument("--pilot", required=True)
    ap.add_argument("--cams", help="comma-separated override of config cameras")
    args = ap.parse_args()

    cfg = load(str(ROOT / "config" / "config.yaml"))
    cams = args.cams.split(",") if args.cams else cfg["cameras"]
    pilot = load_pilot(args.pilot)
    pilot.setup(cfg)

    readers = {
        c: CameraReader(
            c, f"rtsp://{cfg['rtsp_host']}:{cfg['rtsp_port']}/{cfg['rtsp_path'].format(cam=c)}"
        ).start()
        for c in cams
    }
    last = {c: -1 for c in cams}
    lat = LatRecorder(out=str(ROOT / "data" / "metrics" / "frame_latency.csv"))
    try:
        while True:
            for c, r in readers.items():
                got = r.read(after_id=last[c], timeout=0.05)
                if not got:
                    continue
                frame, meta = got  # (np.ndarray, FrameMeta)
                last[c] = meta.frame_id
                for d in pilot.on_frame(frame, meta):
                    if emit_alert(
                        d, meta, args.pilot, root=str(ROOT / "data" / "alerts")
                    ):  # None = dedup grid
                        lat.add(c, time.time() - meta.ts_frame)
            lat.maybe_flush()
    except KeyboardInterrupt:
        pass
    finally:
        lat.flush()
        for r in readers.values():
            r.stop()


if __name__ == "__main__":
    main()
