# Machine profile (to-do 1.4) — 2026-11-19 04:24:52

Platform: Darwin 25.4.0 / arm / cores 10
Load: 4 RTSP fake publishers + 1 dummy pilot worker (4 CameraReaders), video 720p/15fps.

- ffmpeg publishers (4 procs): CPU avg 1.66 cores (17% of 10), RAM peak 100 MB
- pilot worker (python): CPU avg 0.39 cores (4% of 10), RAM peak 282 MB

Verdict (PoC laptop): OK — dưới 50% tổng CPU
