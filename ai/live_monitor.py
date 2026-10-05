"""
Standalone live UFM monitor (CLI) — optional companion to Phase C1 API.

Reads webcam / RTSP / file, runs YOLO, prints confirmed watchlist events.
Prefer the portal Live Monitoring page for demos; use this for headless soak tests.

Usage (from project root, venv active):
  python ai/live_monitor.py --source webcam:0
  python ai/live_monitor.py --source ai/samples/sample_exam_clip.mp4 --persist --camera-id 1
"""

from __future__ import annotations

import argparse
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import cv2
from ultralytics import YOLO

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
AI_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(AI_DIR))

from live_stream import resolve_capture_source  # noqa: E402
from ufm_classes import (  # noqa: E402
    is_ufm_watchlist,
    normalize_label,
    resolve_weights,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Live YOLO monitor (CLI)")
    p.add_argument("--source", type=str, default="webcam:0")
    p.add_argument("--weights", type=str, default=None)
    p.add_argument("--conf", type=float, default=0.35)
    p.add_argument("--min-frames", type=int, default=3)
    p.add_argument("--camera-id", type=int, default=None)
    p.add_argument(
        "--persist",
        action="store_true",
        help="Write confirmed watchlist detections to PostgreSQL",
    )
    p.add_argument("--cooldown", type=float, default=60.0)
    p.add_argument("--show", action="store_true", help="OpenCV preview window")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    weights, mode = resolve_weights(args.weights)
    source = resolve_capture_source(args.source)

    print("=" * 60)
    print("Live monitor (CLI)")
    print(f"source={args.source} -> {source}")
    print(f"weights={weights} mode={mode}")
    print(f"persist={args.persist}")
    print("=" * 60)

    model = YOLO(str(weights))
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        raise SystemExit(f"Could not open source: {args.source}")

    streaks: dict[str, int] = defaultdict(int)
    last_at: dict[str, float] = {}
    frame_index = 0

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                if isinstance(source, str) and Path(source).is_file():
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                time.sleep(0.05)
                continue

            result = model.predict(frame, conf=args.conf, verbose=False)[0]
            labels: dict[str, float] = {}
            if result.boxes is not None:
                for box in result.boxes:
                    cls_id = int(box.cls[0].item())
                    conf = float(box.conf[0].item())
                    raw = result.names.get(cls_id, str(cls_id))
                    label = normalize_label(raw)
                    labels[label] = max(labels.get(label, 0.0), conf)

            active = set(labels)
            for label in list(streaks.keys()):
                if label not in active:
                    streaks[label] = 0

            now = time.monotonic()
            for label, conf in labels.items():
                streaks[label] += 1
                if streaks[label] < args.min_frames:
                    continue
                if not is_ufm_watchlist(label):
                    continue
                if now - last_at.get(label, 0.0) < args.cooldown:
                    continue
                last_at[label] = now
                print(
                    f"CONFIRMED {label} conf={conf:.3f} frame={frame_index}",
                    flush=True,
                )
                if args.persist:
                    _persist(args.camera_id, label, conf, frame_index)

            if args.show:
                preview = result.plot()
                cv2.imshow("VigilantEye live", preview)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

            frame_index += 1
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        cap.release()
        if args.show:
            cv2.destroyAllWindows()


def _persist(
    camera_id: int | None, label: str, confidence: float, frame_index: int
) -> None:
    from database import SessionLocal
    from detection_bridge import notify_detection_alert
    from models.detection import Detection

    db = SessionLocal()
    try:
        row = Detection(
            camera_id=camera_id,
            student_id=None,
            detection_type=label,
            confidence=confidence,
            timestamp=datetime.now(timezone.utc).replace(tzinfo=None),
            is_confirmed=True,
            source_path="cli:live_monitor",
            frame_index=frame_index,
        )
        db.add(row)
        db.flush()
        notify_detection_alert(db, row)
        db.commit()
        print(f"  saved detection #{row.id}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
