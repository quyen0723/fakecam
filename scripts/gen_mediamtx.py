"""Generate scripts/mediamtx.yml from config/config.yaml.

Per playbook §1.4 rule 5 (updated 19/11): the MediaMTX path list must come from the
same source of truth as everything else — never hand-edit the generated file.

Run: .venv/bin/python -m scripts.gen_mediamtx
"""

import sys
from pathlib import Path

from core.config import load

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "scripts" / "mediamtx.yml"

HEADER = """\
# GENERATED from config/config.yaml by scripts/gen_mediamtx.py — do not edit by hand.
# MediaMTX >= 1.21 rejects undeclared paths (playbook §1.4 rule 5).
"""


def render(cfg: dict) -> str:
    lines = [
        HEADER,
        f"rtspAddress: {cfg['rtsp_host']}:{cfg['rtsp_port']}",
        f"rtmpAddress: {cfg['rtsp_host']}:1935",
        f"hlsAddress: {cfg['rtsp_host']}:8888",
        f"webrtcAddress: {cfg['rtsp_host']}:8889",
        "paths:",
    ]
    lines += [f"  {cfg['rtsp_path'].format(cam=cam)}:" for cam in cfg["cameras"]]
    return "\n".join(lines) + "\n"


def main() -> None:
    OUT.write_text(render(load(str(ROOT / "config" / "config.yaml"))))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    sys.exit(main())
