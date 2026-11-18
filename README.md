# fakecam

Fake RTSP cameras (FFmpeg → MediaMTX) + ring buffer + clip services for the
fire-detection PoC. Playbook: `docs/playbook_platform.md`. Code standard: `docs/CODE_STANDARD.md`.

## Quick start (macOS / Linux)

```bash
python3 -m venv .venv && .venv/bin/pip install -e .        # editable install from pyproject
pip install -e .                                            # or: python -m pip install -e .
ffmpeg -y -i raw_sample.mp4 -vf fps=15 -c:v libx264 -g 15 -an videos/cam01.mp4   # normalize per spec
# start MediaMTX (brew install mediamtx / apt):
mediamtx scripts/mediamtx.yml &                             # config is GENERATED — see below
python -m scripts.gen_mediamtx && mediamtx scripts/mediamtx.yml &
python -m fakecam.run_fakecams                              # publishes all cameras, auto-restarts
python -m scripts.read_smoke                                # reads every camera 2 s
open scripts/multiview.html                                 # 4-up browser view (or http.server)
python -m fakecam.run_fakecams stop                         # stops all publishers
```

## Quick start (Windows)

```powershell
# 1. deps: winget install Gyan.FFmpeg ; download mediamtx.exe (github.com/bluenviron/mediamtx)
python -m venv .venv
.venv\Scripts\pip install -e .
# 2. normalize the 4 sample videos (downloads → videos/raw/):
powershell -File scripts\prepare_videos.ps1
# 3. generate + run (all paths from config.yaml):
.venv\Scripts\python -m scripts.gen_mediamtx
.\mediamtx.exe scripts\mediamtx.yml &
.venv\Scripts\python -m fakecam.run_fakecams
.venv\Scripts\python -m scripts.read_smoke
```

Notes: everything binds 127.0.0.1 only (CODE_STANDARD §7). `scripts/mediamtx.yml` is
generated from `config/config.yaml` — do not edit by hand. `data/` and `videos/*.mp4`
are gitignored.

## TLS note (auto.crt/auto.key)

`auto.crt` / `auto.key` are MediaMTX-generated per-machine TLS pairs — never committed,
never copied between machines. The current PoC runs loopback without TLS, so any such
files on disk are local leftovers; they regenerate automatically when a TLS listener
is first needed (per CODE_STANDARD §8).
