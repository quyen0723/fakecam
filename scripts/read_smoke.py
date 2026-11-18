# Smoke test: read frames from all 4 fake cameras (per playbook §3.1 CameraReader pattern)
import os

os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"  # per §1.4 rule 3
import time

import cv2

for i in range(1, 5):
    cam = f"cam0{i}"
    cap = cv2.VideoCapture(
        f"rtsp://127.0.0.1:8554/live/{cam}",
        cv2.CAP_FFMPEG,
        [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000, cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000],
    )
    if not cap.isOpened():
        print(f"{cam}: OPEN FAILED")
        continue
    n, t0 = 0, time.time()
    while time.time() - t0 < 2.0:  # read for 2 seconds
        ok, frame = cap.read()
        if ok and frame is not None:
            n += 1
    cap.release()
    print(f"{cam}: {n} frames in 2.0s (~{n / 2:.1f} fps), shape={frame.shape}")
