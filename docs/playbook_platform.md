# 🛠️ PLAYBOOK KỸ THUẬT PLATFORM SYSTEM (PILOT A/B/C)

> **Ghi chú phạm vi.** Playbook này theo khung prompt gốc, chỉnh 3 chỗ để khớp các quyết định đã chốt:
> - **"Ring buffer"** là vòng đệm các đoạn 2 giây trên đĩa (đoạn cũ bị xóa tự động), không nằm trong RAM của code pilot.
> - **Độ dài clip** đặt trong `config.yaml`, mặc định 10 giây trước + 10 giây sau (muốn 5+5 thì đổi hai số).
> - **p95** đo hai mốc: khung hình → cảnh báo (số chính) và khung hình → hiện trên UI (số phụ).
>
> Code bên dưới là **khung tham khảo, chưa chạy thử trên máy của nhóm**. Các con số đánh dấu *(đề xuất)* cần trưởng dự án hoặc thầy xác nhận.

> **Changelog 19/11/2026**: bug §3.1 `read()` trả (None, None) khi chưa có frame (`_fid=0 > -1` true trước frame đầu) — guard `self._meta is not None`; tìm thấy bằng live test DummyPilot.
> **Changelog 18/11/2026** (sửa theo 2 vòng review — backup bản trước: `playbook_platform.md.20261118.bak`):
> thêm mục 1.4 `config.yaml` + quy tắc nạp config; `CameraReader` log khung hình đầu tiên thay vì lúc mở kết nối, RTSP transport tường minh; `emit_alert` thêm lưới chặn trùng ở Platform; `run_pilot` dùng `LatRecorder` + config; `cut_clip` kiểm tra đủ đoạn; clipper nạp config + chính sách đĩa (>80% dọn mạnh, >95% dừng cắt clip) + dọn clip (synthetic dọn riêng); `supervisor.py` — restart backoff, đếm theo nguồn; bảng rủi ro thêm NTP; runbook 72 giờ; uptime tính riêng Platform/pilot; tuần 1 bổ sung bài test segment trùng. **Không đổi** `cut_clip` về điều kiện chọn segment (giữ `<= t1`, trong dung sai ±2 giây đã chốt).

---

## 1. 🏗️ KIẾN TRÚC LUỒNG DỮ LIỆU & HỢP ĐỒNG ĐẦU NỐI

### 1.1 Luồng dữ liệu

Chạy bằng các tiến trình Python độc lập trên Windows, chưa cần Docker.

```
videos/*.mp4 ─ffmpeg(-re -stream_loop -1)→ [MediaMTX :8554] ─┬─RTSP→ [Recorder: ffmpeg -f segment] → data/rec/{cam}/*.ts (vòng đệm 10 phút)
                                                              ├─RTSP→ [Pilot worker "fire":   CameraReader → on_frame()] ─┐
                                                              └─RTSP→ [Pilot worker "person": CameraReader → on_frame()] ─┤ emit_alert()
                                                                                                                          ↓
                                              data/alerts/{cam}/{alert_id}.json ──→ [Clipper] → data/clips/{cam}/{alert_id}.mp4
                                              alerts + clips + reviews.csv ──→ [Streamlit dashboard]
```

Hai quyết định thiết kế quan trọng:

1. **Mỗi worker pilot tự giữ `CameraReader` cho các camera của mình.** Khung hình không phải truyền qua lại giữa các tiến trình (720p có khoảng 2,7 MB mỗi khung, truyền qua queue rất tốn). Chỉ cảnh báo nhỏ mới đi qua file JSON.
2. **Reader chỉ giữ khung hình mới nhất, không dùng hàng đợi.** Model chạy chậm thì tự bỏ khung cũ. Đây là cách chống "frame accumulation delay" từ gốc.

### 1.2 Hợp đồng với hai nhóm pilot

Nhóm pilot chỉ cần viết một class theo interface này, không cần đụng RTSP, file, clip:

```python
# core/contract.py
from dataclasses import dataclass
from typing import Optional, Protocol, Sequence
import numpy as np


@dataclass(frozen=True)
class FrameMeta:
    camera_id: str
    frame_id: int  # tăng dần theo từng camera
    ts_frame: float  # time.time() lúc reader nhận khung hình


@dataclass
class AlertDraft:
    event_type: str  # fire | smoke | intrusion | dwell
    confidence: float
    bbox: Optional[Sequence[int]] = None
    model_version: str = ""


class Pilot(Protocol):
    name: str

    def setup(self, cfg: dict) -> None: ...
    def on_frame(self, frame: np.ndarray, meta: FrameMeta) -> list[AlertDraft]: ...
```

**Cảnh báo ra đĩa** (Platform tự sinh từ `AlertDraft`, pilot không tự ghi file):

```json
{
  "alert_id": "cam01_1763280000123_fire",
  "camera_id": "cam01",
  "pilot": "fire",
  "event_type": "fire",
  "frame_id": 4521,
  "ts_frame": 1763280000.123,
  "ts_alert": 1763280000.456,
  "confidence": 0.87,
  "bbox": [412, 220, 80, 64],
  "model_version": "yolo-d-fire-v1"
}
```

**Bốn quy tắc cho pilot** (đưa vào trang hợp đồng):

1. `on_frame` phải **giữ trạng thái riêng cho từng camera** (dict theo `camera_id`), vì logic "15 trên 20 khung" là theo camera.
2. Cửa sổ thời gian nên tính **theo giây**, không theo số khung. Khi model chậm, reader bỏ khung, nên "20 khung" có thể kéo dài hơn dự tính.
3. `ts_frame` của cảnh báo là khung **kích hoạt** quy tắc. Đoạn chờ của logic thời gian thuộc detection delay do nhóm Lửa chấm, không tính vào p95 của Platform.
4. Tự áp **cooldown** (đề xuất 30 giây cho mỗi cặp camera và loại sự kiện) và giới hạn bộ nhớ các cấu trúc tracking (ByteTrack giữ ID mãi sẽ rò rỉ).

Pilot C (đếm người theo thời gian) chưa nằm trong hợp đồng này. Tạm cho ghi riêng `data/counts/{cam}.csv`, bổ sung sau.

### 1.3 Cấu trúc thư mục

```
platform/
  config.yaml              # cameras, profile video, pre/post, seg_s, keep_s
  fakecam/run_fakecams.py  # script phát camera giả + tự restart
  fakecam/prepare_videos.ps1   # chuẩn hóa video (H.264, 720p, 15 fps, -g 15)
  core/contract.py  camera_reader.py  clip_buffer.py  alerts.py  run_pilot.py
  pilots/fire/  pilots/person/  pilots/dummy.py   # nhóm Lửa / Người / giả lập
  services/clipper.py  supervisor.py
  dashboard/app.py
  tools/inject_alert.py  soak_monitor.py  latency_report.py
  data/{rec,alerts,clips,logs,metrics}/
```

`pilots/dummy.py` (cứ 30 giây bắn một cảnh báo) cho phép Platform test toàn bộ đường ống mà không chờ model của hai nhóm.

### 1.4 `config.yaml` mẫu — nguồn duy nhất của các con số và đường dẫn

```yaml
rtsp_host: "127.0.0.1"        # bind/reach loopback (§7) — đổi chỉ khi mở LAN có lý do trong PR
rtsp_port: 8554
hls_port: 8888                # trình duyệt — multiview đọc từ đây, không hardcode
rtmp_port: 1935
webrtc_port: 8889
rtsp_path: "live/{cam}"       # URL đầy đủ = rtsp://{rtsp_host}:{rtsp_port}/{rtsp_path}
cameras: [cam01, cam02, cam03, cam04]
pre: 10          # giây trước cảnh báo
post: 10         # giây sau cảnh báo
seg_s: 2         # độ dài mỗi đoạn vòng đệm trên đĩa
keep_s: 600      # giữ đoạn ghi 10 phút
cooldown_s: 30   # lưới chặn trùng ở Platform (xem mục 3.3)
```

Quy tắc khi nạp config:

1. **`camera_id` phải khớp mẫu `^cam\d{2}$`.** Thư mục Windows không phân biệt hoa/thường, nhưng đường dẫn RTSP của MediaMTX thì có — sai tên là mất clip âm thầm. Kiểm tra ngay lúc nạp config, sai thì thoát kèm thông báo. Nạp config còn kiểm: `rtsp_path` chứa `{cam}`, `rtsp_port` 1–65535, các số `pre/post/seg_s/keep_s/cooldown_s` > 0.
2. **Không hardcode URL/port ở bất kỳ module nào.** `run_fakecams`, recorder, `CameraReader`, clipper dùng `rtsp_host` + `rtsp_port` + `rtsp_path` từ config. URL chỉ tồn tại ở một chỗ. *(Cập nhật 19/11 sau review: port trước đây hardcode `8554` trong code là vi phạm — đã chuyển sang config.)*
3. **RTSP transport đặt tường minh**, không phụ thuộc mặc định của OpenCV: đặt
   `os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"` **trước `import cv2`** và dùng `-rtsp_transport tcp` cho mọi dòng lệnh FFmpeg. Đây là chọn cho nhất quán, không phải sửa lỗi UDP.
4. Dùng `shutil.disk_usage` để lấy `% đĩa trống` cho chính sách đĩa của Clipper (mục 3.2) và `soak_monitor` (mục 5.2).
5. **MediaMTX ≥ 1.21 yêu cầu khai báo path tường minh** (`paths:` trong config) — path không khai báo thì push bị từ chối ("Server returned 400 Bad Request", log: *path is not configured*; đã gặp thật khi dựng 4 camera 18/11). **`scripts/mediamtx.yml` KHÔNG được sửa tay — sinh bằng `python -m scripts.gen_mediamtx` từ `config.yaml`** (chỉ một nguồn sự thật; review 19/11: file tĩnh hai nguồn là rủi ro quên đồng bộ). *(Bổ sung 18/11, cập nhật 19/11.)*
6. **Tin số liệu p95 chỉ sau phép đo drawtext** (mục 5.1): OpenCV `cap.read()` có thể trả frame từ buffer (hộp thử 18/11: stream 15 fps đọc ra ~25 frame/s) — FPS theo vòng loop không phải bằng tốc độ phát thật. Chạy phép đo watermark `drawtext` (20 mẫu, mục 5.1) trước khi tin `frame_latency.csv`. *(Bổ sung 18/11.)*

---

## 2. 📅 LỘ TRÌNH TRIỂN KHAI TỪNG BƯỚC

| Mốc | Làm gì | Pass khi |
|---|---|---|
| **Ngày 1–3** | Chốt hợp đồng (mục 1), số camera, `config.yaml`, repo chung. Viết `prepare_videos.ps1`. Viết `DummyPilot` | Hai nhóm pilot xác nhận hợp đồng bằng tin nhắn. `DummyPilot` chạy qua `run_pilot` |
| **Tuần 1** | Cài MediaMTX, FFmpeg. `run_fakecams.py` chạy 4 camera, tự restart. `CameraReader` bản 1, giao cho hai nhóm dùng ngay | 4 camera chạy ≥1 giờ. Kill một FFmpeg thì tự sống lại. Hai nhóm đọc được khung hình qua `CameraReader` |
| **Tuần 1 bổ sung** (rủi ro tên segment trùng) | Bài test thật: chạy recorder 10 phút → tắt MediaMTX 60 giây → bật lại, chạy thêm 10 phút | Liệt kê tên file trong `data/rec/{cam}`: không có tên trùng; nếu trùng (dồn gói dồn cục khi nối lại), áp dụng cách sửa đã chốt — so số đoạn thiếu trong `cut_clip` (mục 3.2) và ghi vào `clip_gaps.csv` |
| **Tuần 2** (mốc đề bài) | `CameraReader` bản cứng (backoff, treo luồng, log). Recorder + dọn đoạn cũ + Clipper. `inject_alert.py` bắn cảnh báo giả | 4 camera ≥1 giờ. 3 kịch bản mất luồng (kill FFmpeg, tắt MediaMTX, luồng treo) đều tự nối lại ≤30 giây, không crash. Bắn 20 cảnh báo giả, ≥19 có clip đúng độ dài (±2 giây) mở được bằng trình duyệt |
| **Tuần 3** | Cắm pilot thật vào `run_pilot`. Ghi độ trễ từng khung. Streamlit (feed, clip, nút xác nhận, ghi `ts_ui`). Chạy thử 24 giờ với pilot thật | 24 giờ không tiến trình nào chết vĩnh viễn. RAM không tăng liên tục. Cảnh báo hiện trên UI trong vòng ~2 lần chu kỳ làm mới |
| **Tuần 4** | Ngày 1–2: bắt đầu chạy 72 giờ (full stack). Chèn sự cố theo kịch bản. Ngày 5: báo cáo p95 và ổn định | Đạt tiêu chí mục 5 |

**Lưu ý lịch:** 72 giờ là 3 ngày thật. Bắt đầu muộn nhất ngày 2 của tuần 4. Nếu pilot sẵn sàng từ cuối tuần 3 thì chạy sớm hơn, để còn một lần chạy lại nếu crash.

---

## 3. 💻 MẪU CODE KIẾN TRÚC CỐT LÕI

### 3.1 `CameraReader`: đọc RTSP, tự nối lại, chỉ giữ khung mới nhất

```python
# core/camera_reader.py
# LƯU Ý: môi trường phải đặt TRƯỚC khi import cv2 (xem mục 1.4 — quy tắc 3):
#   os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"
import cv2, time, threading, csv
from pathlib import Path
from core.contract import FrameMeta


class CameraReader:
    def __init__(self, camera_id, url, log_dir="data/logs", stall_s=5.0, max_backoff=10.0):
        self.id, self.url = camera_id, url
        self.stall_s, self.max_backoff = stall_s, max_backoff
        self._cv = threading.Condition()
        self._frame, self._meta, self._fid = None, None, 0
        self._stop = threading.Event()
        self._log = Path(log_dir) / "reconnect.csv"
        self._log.parent.mkdir(parents=True, exist_ok=True)
        self._t = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._t.start()
        return self

    def stop(self):
        self._stop.set()

    def read(self, after_id=-1, timeout=1.0):
        """Trả (frame, meta) MỚI NHẤT có frame_id > after_id, hoặc None nếu hết timeout."""
        with self._cv:
            # _fid khởi tạo = 0 nên `_fid > -1` là TRUE cả khi CHƯA có frame
            # (bug phát hiện 19/11 bằng live test: read() trả (None, None) → crash)
            self._cv.wait_for(lambda: self._meta is not None and self._fid > after_id, timeout)
            if self._meta is None or self._fid <= after_id:
                return None
            return self._frame, self._meta

    def _open(self):
        # Timeout chỉ có từ OpenCV 4.5.2 trở lên; kiểm tra phiên bản đang dùng
        return cv2.VideoCapture(
            self.url,
            cv2.CAP_FFMPEG,
            [
                cv2.CAP_PROP_OPEN_TIMEOUT_MSEC,
                5000,
                cv2.CAP_PROP_READ_TIMEOUT_MSEC,
                5000,
            ],
        )

    def _log_event(self, lost, back, reason):
        with open(self._log, "a", newline="") as f:
            csv.writer(f).writerow(
                [self.id, f"{lost:.3f}", f"{back:.3f}", f"{back - lost:.1f}", reason]
            )

    def _run(self):
        backoff, lost_at = 1.0, None
        while not self._stop.is_set():
            cap = self._open()
            if cap.isOpened():
                got_first = False
                last_ok = time.time()  # mốc bắt đầu chờ khung đầu
                while not self._stop.is_set():
                    ok, frame = cap.read()
                    now = time.time()
                    if not ok or frame is None:
                        if now - last_ok > self.stall_s:  # mất hoặc treo luồng
                            lost_at = lost_at or last_ok
                            break
                        time.sleep(0.05)
                        continue
                    if not got_first:
                        got_first = True
                        # Log khi có KHUNG ĐẦU TIÊN, không phải khi mở được kết nối —
                        # mở xong nhưng luồng chưa chảy vẫn phải tính là gián đoạn.
                        if lost_at is not None:
                            self._log_event(lost_at, now, "first_frame")
                            lost_at = None
                        backoff = 1.0
                    last_ok = now
                    with self._cv:  # chỉ giữ khung mới nhất
                        self._fid += 1
                        self._frame = frame
                        self._meta = FrameMeta(self.id, self._fid, now)
                        self._cv.notify_all()
            cap.release()
            lost_at = lost_at or time.time()
            time.sleep(backoff)
            backoff = min(backoff * 2, self.max_backoff)
```

### 3.2 Vòng đệm đoạn 2 giây trên đĩa và cắt clip

```python
# core/clip_buffer.py
import csv, subprocess, time
from datetime import datetime
from pathlib import Path

SEG_S = 2


def start_recorder(cam, url, rec_dir="data/rec"):
    d = Path(rec_dir) / cam
    d.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-rtsp_transport",
        "tcp",
        "-i",
        url,
        "-c",
        "copy",
        "-an",
        "-f",
        "segment",
        "-segment_time",
        str(SEG_S),
        "-strftime",
        "1",
        "-reset_timestamps",
        "1",
        str(d / "%Y%m%d_%H%M%S.ts"),
    ]
    return subprocess.Popen(
        cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )  # supervisor restart nếu thoát


def _start_ts(p: Path) -> float:
    return datetime.strptime(p.stem, "%Y%m%d_%H%M%S").timestamp()


def prune(cam, keep_s=600, rec_dir="data/rec"):
    cut = time.time() - keep_s
    for p in (Path(rec_dir) / cam).glob("*.ts"):
        try:
            if _start_ts(p) < cut:
                p.unlink()
        except (OSError, ValueError):
            pass  # Windows: file đang bị đọc thì để lần sau


def cut_clip(cam, ts_frame, pre, post, out: Path, rec_dir="data/rec") -> bool:
    t0, t1 = ts_frame - pre, ts_frame + post
    segs = sorted(p for p in (Path(rec_dir) / cam).glob("*.ts") if t0 - SEG_S <= _start_ts(p) <= t1)
    # Kiểm tra đủ đoạn (rủi ro "tên segment trùng" — hai đoạn sinh cùng 1 giây bị ghi đè):
    # thiếu ≥ 2 đoạn so với kỳ vọng (pre+post)/SEG_S → ghi log, clip vẫn cắt (best effort).
    missing = (pre + post) // SEG_S - len(segs)
    gap_log = Path(rec_dir) / ".." / "logs" / "clip_gaps.csv"
    if missing >= 2:
        gap_log.parent.mkdir(parents=True, exist_ok=True)
        with open(gap_log, "a", newline="") as f:
            csv.writer(f).writerow([time.strftime("%F %T"), cam, int(ts_frame), str(missing)])
    if not segs:
        return False
    out.parent.mkdir(parents=True, exist_ok=True)
    lst = out.with_suffix(".txt")
    lst.write_text("".join(f"file '{p.resolve().as_posix()}'\n" for p in segs))
    r = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(lst),
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            str(out),
        ]
    )
    lst.unlink(missing_ok=True)
    return r.returncode == 0
```

```python
# services/clipper.py (khung) — PRE/POST/CAMS/seg từ config.yaml (mục 1.4), không còn biến tự do
from core.config import C

PRE, POST, CAMS, SEG_S = C["pre"], C["post"], C["cameras"], C["seg_s"]

import json, shutil, time
from pathlib import Path


def disk_free_ratio(path: str) -> float:
    u = shutil.disk_usage(path)
    return u.free / u.total


done = set()
while True:
    free = disk_free_ratio("data")
    # Chính sách đĩa (phản ứng, không chỉ ghi số — soak_monitor theo dõi tiếp):
    #   >80% đầy  → prune mạnh đoạn ghi (keep_s giảm tạm còn 300 giây)
    #   >95% đầy  → DỪNG cắt clip (thu phạm chính là clip); cảnh báo JSON vẫn ghi,
    #               vẫn hiện trên UI kèm "không có clip" — p95/uptime không bị ảnh hưởng.
    stop_cut = free < 0.05
    keep_now = 300 if free < 0.20 else C["keep_s"]
    for f in Path("data/alerts").glob("*/*.json"):
        if f in done or stop_cut:
            continue
        a = json.loads(f.read_text())
        # chờ đủ đoạn "sau" + 1 đoạn đang ghi dở + 1 giây dự phòng
        if time.time() < a["ts_frame"] + POST + SEG_S + 1:
            continue
        out = Path("data/clips") / a["camera_id"] / f"{a['alert_id']}.mp4"
        if cut_clip(a["camera_id"], a["ts_frame"], PRE, POST, out):
            done.add(f)
    for cam in CAMS:
        prune(cam, keep_s=keep_now)
    prune_clips(
        max_keep_days=C.get("clip_keep_days", 3), exclude_synthetic=True
    )  # clip của cảnh báo synthetic dọn riêng (xem dưới)
    time.sleep(1)


def prune_clips(root="data/clips", max_keep_days=3, exclude_synthetic=True):
    """Vòng dọn clip: cảnh báo synthetic (inject_alert) xóa ngay sau khi kiểm tra;
    clip thật giữ theo hạn ngày. 72h × 1 cảnh báo/phút ≈ 4.300 clip ≈ 12–24 GB,
    không dọn là đầy đĩa trong 72 giờ."""
    cut = time.time() - max_keep_days * 86400
    for p in Path(root).glob("*/*.mp4"):
        try:
            if p.stat().st_mtime < cut:
                p.unlink()
        except OSError:
            pass  # Windows khóa file — để lần quét sau
```

**Alerts synthetic** (từ `inject_alert.py`) mang thêm trường `"synthetic": true` trong JSON — Clipper/UI nhận ra được, vòng dọn ưu tiên xóa ngay sau khi kiểm tra, không tính vào số liệu nghiệm thu clip thật.

### 3.3 Chạy pilot và ghi cảnh báo

```python
# core/alerts.py
import json, os, time
from pathlib import Path

_last: dict[tuple, float] = {}  # (event_type, camera_id) → ts cảnh báo gần nhất


def emit_alert(d, meta, pilot_name, root="data/alerts", cooldown_s=30):
    now = time.time()
    key = (d.event_type, meta.camera_id)
    # Lưới an toàn của Platform (độc lập với cooldown nội bộ của pilot — mục 1.2 quy tắc 4):
    # cùng camera + loại sự kiện trong cooldown_s thì bỏ qua. Cảnh báo JSON rất nhỏ,
    # thủ phạm làm đầy đĩa là CLIP — lưới này chặn ở nguồn nên clip cũng không sinh ra.
    if now - _last.get(key, 0.0) < cooldown_s:
        return None
    _last[key] = now
    a = {
        "alert_id": f"{meta.camera_id}_{int(now * 1000)}_{d.event_type}",
        "camera_id": meta.camera_id,
        "pilot": pilot_name,
        "event_type": d.event_type,
        "frame_id": meta.frame_id,
        "ts_frame": meta.ts_frame,
        "ts_alert": now,
        "confidence": d.confidence,
        "bbox": d.bbox,
        "model_version": d.model_version,
    }
    p = Path(root) / meta.camera_id / f"{a['alert_id']}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(a))
    os.replace(tmp, p)  # ghi nguyên tử, Clipper và UI không đọc phải file ghi dở
```

```python
# core/latency.py — ghi độ trễ từng khung, xả ra CSV mỗi 5 giây
import csv, time
from pathlib import Path


class LatRecorder:
    def __init__(self, out="data/metrics/frame_latency.csv"):
        self.out, self.buf = Path(out), []
        self.out.parent.mkdir(parents=True, exist_ok=True)
        self.out.write_text("camera,ts,lat_s\n")  # tiêu đề, bỏ qua khi chạy lại

    def add(self, cam, lat_s):
        self.buf.append([cam, f"{time.time():.3f}", f"{lat_s:.4f}"])

    def flush(self):
        if self.buf:
            with open(self.out, "a", newline="") as f:
                csv.writer(f).writerows(self.buf)
            self.buf.clear()
```

```python
# core/run_pilot.py  →  python -m core.run_pilot --pilot fire --cams cam01,cam02
from core.config import C

CAMS = C["cameras"]
readers = {
    c: CameraReader(c, f"rtsp://localhost:8554/{C['rtsp_path'].format(cam=c)}").start()
    for c in CAMS
}
last = {c: -1 for c in CAMS}
while True:
    for c, r in readers.items():
        got = r.read(after_id=last[c], timeout=0.05)
        if not got:
            continue
        frame, meta = got
        last[c] = meta.frame_id
        for d in pilot.on_frame(frame, meta):
            if emit_alert(d, meta, pilot.name):  # None = bị lưới chặn trùng (mục 3.3)
                lat.add(
                    c, time.time() - meta.ts_frame
                )  # on_frame trả về − ts_frame, xả CSV mỗi 5 giây
```

### 3.4 Streamlit: chỉ làm mới một vùng, không chạy lại cả trang

```python
# dashboard/app.py  (cần Streamlit >= 1.37 cho st.fragment)
import streamlit as st, json, time, csv
from pathlib import Path

st.set_page_config(layout="wide")


@st.cache_resource
def seen():
    return set()  # alert đã ghi ts_ui


@st.fragment(run_every=2)
def feed():
    files = sorted(
        Path("data/alerts").glob("*/*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )[:30]
    for f in files:
        a = json.loads(f.read_text())
        if a["alert_id"] not in seen():
            seen().add(a["alert_id"])
            with open("data/metrics/ui_seen.csv", "a", newline="") as m:
                csv.writer(m).writerow([a["alert_id"], f"{time.time():.3f}"])  # ts_ui
        with st.container(border=True):
            st.write(f"**{a['camera_id']}** · {a['event_type']} · {a['confidence']:.2f}")
            clip = Path("data/clips") / a["camera_id"] / f"{a['alert_id']}.mp4"
            st.video(str(clip)) if clip.exists() else st.caption("Đang cắt clip…")
            c1, c2 = st.columns(2)
            for col, label in ((c1, "Đúng"), (c2, "Sai")):
                if col.button(label, key=f"{a['alert_id']}_{label}"):
                    with open("data/reviews.csv", "a", newline="") as r:
                        csv.writer(r).writerow([a["alert_id"], label, f"{time.time():.3f}"])


feed()
```

### 3.4 `supervisor.py` — giám sát tiến trình, restart có backoff, đếm theo nguồn

Pass-criteria tuần 1 ("kill một FFmpeg thì tự sống lại") và 72 giờ phụ thuộc vào đây. Ai giám sát supervisor: PoC chấp nhận nó là điểm đơn (tiến trình rất nhỏ); nếu chạy trên máy luôn awake đã tắt Windows Update, thêm Task Scheduler "restart on failure" và ghi rõ vào tiêu chí nghiệm thu.

```python
# services/supervisor.py (khung)
import csv, subprocess, time
from pathlib import Path

RESTART_LOG = Path("data/metrics/restarts.csv")


def supervise(procs: dict[str, dict], poll_s=2.0, restart_backoff_max=60):
    """procs: {name: {"cmd": [...], "source": "platform" | "pilot"}}
    Ý nghĩa của "source": số restart được đếm riêng theo nguồn để tính uptime —
    lỗi do pilot KHÔNG tính vào uptime của Platform (xem mục 5.3)."""
    RESTART_LOG.parent.mkdir(parents=True, exist_ok=True)
    info = {n: {"p": None, "next_ok": 0.0, "backoff": 1.0, **v} for n, v in procs.items()}
    while True:
        for name, it in info.items():
            if it["p"] is None or it["p"].poll() is not None:
                now = time.time()
                if now < it["next_ok"]:
                    continue  # backoff: chưa đến lúc restart lại
                if it["p"] is not None:  # đây là một lần chết thật
                    with open(RESTART_LOG, "a", newline="") as f:
                        csv.writer(f).writerow(
                            [
                                time.strftime("%F %T"),
                                name,
                                it["source"],
                                f"{now:.0f}",
                                it["backoff"],
                            ]
                        )
                    it["backoff"] = min(it["backoff"] * 2, restart_backoff_max)
                    it["next_ok"] = now + it["backoff"]
                it["p"] = subprocess.Popen(it["cmd"])
        time.sleep(poll_s)
```

Supervisor giám sát: tiến trình phát camera giả (`run_fakecams.py`), recorder từng camera, và từng worker pilot. Worker pilot do Platform restart; số restart ghi `source: "pilot"`, tách riêng khi báo cáo (mục 5.3).

---

## 4. ⚠️ BẢNG QUẢN TRỊ RỦI RO KỸ THUẬT

| Rủi ro | Nguyên nhân sâu xa | Cách xây đúng từ đầu |
|---|---|---|
| **Frame accumulation delay** (độ trễ tăng dần) | Hàng đợi khung hình; model chậm hơn tốc độ camera | Reader chỉ giữ khung mới nhất, bỏ khung cũ; không dùng queue không giới hạn; log độ trễ từng khung để phát hiện trôi |
| **Đọc RTSP bị treo vĩnh viễn** | `cap.read()` chờ mãi khi luồng treo; timeout của OpenCV tùy phiên bản | Đặt timeout mở và đọc (OpenCV ≥ 4.5.2), cộng thêm đồng hồ `stall_s`. Nếu vẫn treo thì tách mỗi camera một tiến trình để supervisor kill được |
| **Rò rỉ bộ nhớ OpenCV** | Mở `VideoCapture` mới mà không `release()`; giữ danh sách khung hình trong code pilot | Luôn `release()` trước khi mở lại. Cấm giữ khung hình trong list không giới hạn. Theo dõi RAM từng tiến trình từ tuần 3 |
| **Rò rỉ ở tracker** (ByteTrack giữ ID mãi) | Dict track không bao giờ dọn | Điều khoản trong hợp đồng pilot: giới hạn lịch sử, dọn track hết hạn |
| **FFmpeg bị nghẽn** | Dùng `stdout=PIPE` mà không ai đọc | Dùng `DEVNULL` hoặc ghi ra file log |
| **Đầy đĩa** | Đoạn ghi và clip tăng mãi, lặp vòng video cháy sinh cảnh báo dồn dập | Dọn đoạn cũ hơn 10 phút; cooldown 30 giây ở pilot; giới hạn số clip giữ lại; giám sát dung lượng đĩa trong soak |
| **Cắt clip sai hoặc ngắn** | Nén thông minh làm keyframe thưa; `-c copy` chỉ cắt tại keyframe | Chuẩn hóa video với `-g 15`; khi lắp camera thật phải kiểm tra khoảng keyframe |
| **Windows khóa file** | Xóa đoạn đang được đọc bởi clipper | Bọc `try/except`, thử lại lần quét sau |
| **Push bị MediaMTX từ chối (400)** | MediaMTX ≥ 1.21 đòi path khai báo tường minh; lỗi rơi ở FFmpeg publisher ("Server returned 400 Bad Request") | Sinh `mediamtx.yml` từ `config.yaml` (quy tắc 1.4.5); publisher retry có backoff như CameraReader |
| **Streamlit giật, chạy lại cả trang** | Mỗi tương tác chạy lại toàn bộ script; quét thư mục lớn | `st.fragment(run_every=2)`; chỉ hiển thị 30 cảnh báo gần nhất; không phát khung hình trực tiếp qua Streamlit |
| **Máy ngủ hoặc tự cập nhật trong 72 giờ** | Cài đặt nguồn và Windows Update | Tắt sleep, tắt tự khởi động lại; ghi nhận và loại khỏi số liệu uptime nếu xảy ra ngoài ý muốn |
| **Cảnh báo giả do vòng lặp video** | Điểm nối giật hình tạo chuyển động | Cắt video sao cho đầu và cuối khớp, hoặc đánh dấu vùng nối khi chấm |
| **Đồng hồ máy bị chỉnh giữa chừng** | Windows đồng bộ NTP tự động; `ts_frame`/`ts_alert`/tên segment lệch pha → p95 sai, cắt clip sai | Tắt đồng bộ giờ tự động trong 72 giờ; `soak_monitor` ghi thời điểm NTP nhảy (nếu có), loại các mẫu quanh thời điểm đó khỏi p95 |
| **Chạy hai pilot trên cùng camera** | Mỗi worker giải mã riêng, tốn CPU/GPU | Chấp nhận trong PoC, ghi vào cấu hình máy khi báo cáo; MediaMTX cho phép nhiều reader |
| **Số p95 quá đẹp do chạy 720p/15 fps** | Camera thật thường 1080p/25 fps | Từ tuần 3, đo p95 và chạy 72 giờ bằng profile 1080p/25 fps |

---

## 5. 🧪 KỊCH BẢN BENCHMARK P95 & STRESS-TEST 72H

### 5.1 Đo p95

| Chỉ số | Công thức | Nguồn mẫu |
|---|---|---|
| **p95 xử lý (chính)** | `thời điểm on_frame trả về − ts_frame`, mọi khung | Hàng chục nghìn mẫu từ `frame_latency.csv` |
| **p95 cảnh báo** | `ts_alert − ts_frame` | Từng cảnh báo |
| **p95 hiện trên UI (phụ)** | `ts_ui − ts_frame` | `ui_seen.csv`; dùng `inject_alert.py` bắn 1 cảnh báo mỗi phút, khoảng 4.300 mẫu trong 72 giờ |
| **Độ trễ clip** | thời điểm file clip xuất hiện − `ts_alert` | Mỗi cảnh báo; kỳ vọng ≈ `post` + vài giây |
| **Độ trễ luồng RTSP** (camera giả → reader) | Chèn đồng hồ bằng `drawtext`, so với giờ máy | Đo tay khoảng 20 mẫu, một lần mỗi profile |

Tính toán:

```python
import pandas as pd

d = pd.read_csv("data/metrics/frame_latency.csv")  # camera, ts, lat_s
print(d.groupby("camera").lat_s.describe(percentiles=[0.5, 0.95, 0.99]))
```

Báo cáo p50, p95, p99, max theo từng camera, kèm cấu hình máy và profile video. Đồng hồ chung vì cùng một máy.

### 5.2 Kịch bản 72 giờ (full stack)

- **Cấu hình:** 4 camera, hai pilot thật, Streamlit, recorder, clipper, `soak_monitor.py`.
- **`soak_monitor.py`** ghi mỗi 30 giây: RAM và CPU từng tiến trình (`psutil`), GPU (`nvidia-smi --query-gpu`), dung lượng đĩa, số lần mất luồng, số lần supervisor khởi động lại. **Phản ứng khi đĩa cạn** xử lý ở Clipper (mục 3.2: >80% dọn mạnh, >95% dừng cắt clip) — soak chỉ theo dõi và ghi; nếu đĩa vẫn cạn dưới 2% thì cảnh báo (âm thanh/log nổi bật) gọi người trực.
- **Sự cố cố ý:** mỗi 2 giờ kill ngẫu nhiên một FFmpeg phát camera; giờ 24 tắt MediaMTX 60 giây; giờ 48 tạm dừng (suspend) một FFmpeg để mô phỏng luồng treo.
- **Tải liên tục:** `inject_alert.py` bắn cảnh báo giả mỗi phút để thử clip và UI suốt 72 giờ (mang `synthetic: true` — mục 3.2).

#### Runbook trong 72 giờ — ai làm gì khi có sự cố

| Tín hiệu từ `soak_monitor` | Người trực làm gì |
|---|---|
| RAM một tiến trình tăng dần qua 2 lần quét liên tiếp | Ghi lại tên + giờ vào log; **không restart vội** (làm mất mẫu p95 liên tục). Nếu RAM vượt quá quy ước trước khi bắt đầu (ví dụ ×2 từ lúc bắt đầu) → restart tiến trình đó bằng supervisor, ghi `restart_count` nguồn |
| Đĩa >80% | Đã có Clipper tự dọn mạnh (mục 3.2). Kiểm tra `clip_gaps.csv` và `restarts.csv` xem có nguồn sinh ra lạ không |
| Đĩa >95% (Clipper dừng cắt clip) | Hệ vẫn chạy, cảnh báo JSON vẫn đổ về. **Không tắt hệ thống.** Ghi giờ bắt đầu/kết thúc, báo cáo có dòng "không có clip" từ giờ X đến giờ Y |
| Luồng treo / FFmpeg chết | Supervisor tự restart (tuần 1 đã pass kịch bản này). Chỉ can thiệp nếu cùng tiến trình chết ≥3 lần trong 1 giờ |
| Nghi ngờ đồng hồ bị chỉnh | So 2 nguồn giờ (lệnh `time` và `ts_alert` mới nhất), ghi lại thời điểm nghi nhảy; mẫu quanh đó loại khỏi p95 khi phân tích |

### 5.3 Tiêu chí nghiệm thu *(đề xuất, cần trưởng dự án xác nhận)*

| Tiêu chí | Ngưỡng |
|---|---|
| Hoàn thành 72 giờ liên tục | Không tiến trình nào chết vĩnh viễn |
| Uptime hệ thống | ≥ 99% (tổng gián đoạn ≤ 43 phút) — **tính riêng theo nguồn** (`restarts.csv` cột `source`): lỗi từ Platform (fakecam/MM/recorder/clipper) tính vào uptime; lỗi do pilot/model nhóm bạn báo riêng, không cộng vào Platform |
| Nối lại sau mất luồng | ≥ 95% số lần trong ≤ 30 giây |
| RAM mỗi tiến trình | Sau giờ thứ 2, không tăng liên tục (độ dốc ≈ 0, tăng không quá 5%) |
| Dung lượng đĩa | Nằm trong giới hạn, không tăng tuyến tính |
| Clip | ≥ 95% cảnh báo có clip đúng độ dài |
| p95 xử lý | Báo cáo số kèm cách đo; ngưỡng tham khảo ≤ 1 giây (chưa có yêu cầu chính thức) |

Nếu crash giữa chừng thì sửa lỗi rồi chạy lại từ đầu, ghi nguyên nhân vào báo cáo.
