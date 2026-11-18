# fakecam

Fake RTSP cameras (FFmpeg → MediaMTX) + ring buffer + clip services for the
fire-detection PoC. Playbook: `docs/playbook_platform.md`. Code standard: `docs/CODE_STANDARD.md`.

## Quick start (macOS / Linux)

```bash
python3 -m venv .venv && .venv/bin/pip install -e .      # deps from pyproject
.venv/bin/python -m scripts.gen_mediamtx                 # generate scripts/mediamtx.yml from config (never hand-edit)
mediamtx scripts/mediamtx.yml &                          # brew/apt install; binds 127.0.0.1 only
.venv/bin/python -m fakecam.run_fakecams                 # publishes all cameras, watchdog auto-restart
.venv/bin/python -m scripts.read_smoke                   # verify: reads every camera 2 s
(.venv/bin/python -m http.server 8800 --bind 127.0.0.1 &) ; open http://127.0.0.1:8800/scripts/multiview.html
.venv/bin/python -m fakecam.run_fakecams stop            # stops all publishers (pid-guarded)
```

Normalize sample videos once (H.264 720p 15fps g=15 per playbook §1.3):
```bash
for f in videos/raw/*.mp4; do ffmpeg -y -i "$f" -vf fps=15 -c:v libx264 -preset veryfast -g 15 -an "videos/$(basename "${f%.*}").mp4"; done
# then rename outputs to cam01.mp4 .. cam04.mp4 (order matches config.yaml cameras)
```

## Quick start (Windows)

```powershell
# 1. deps: winget install Gyan.FFmpeg ; download mediamtx.exe (github.com/bluenviron/mediamtx)
python -m venv .venv ; .venv\Scripts\pip install -e .
# 2. normalize the 4 sample videos (files in videos\raw\):
powershell -File scripts\prepare_videos.ps1
# 3. generate config, start mediamtx (PowerShell has no `&` → Start-Process):
.venv\Scripts\python -m scripts.gen_mediamtx
Start-Process -NoNewWindow .\mediamtx.exe -ArgumentList "scripts\mediamtx.yml"
# 4. run + verify:
.venv\Scripts\python -m fakecam.run_fakecams
.venv\Scripts\python -m scripts.read_smoke
```

## Notes

- Everything binds 127.0.0.1 only (CODE_STANDARD §7). Open LAN ports only with a PR reason.
- `scripts/mediamtx.yml` is generated from `config/config.yaml` — do not edit by hand.
- Gitignored: `data/`, `videos/` (samples stay local; `.gitkeep` keeps the dir).
- `auto.crt`/`auto.key` are MediaMTX per-machine TLS pairs — never committed, never copied
  between machines; loopback PoC needs no TLS (see CODE_STANDARD §8).
