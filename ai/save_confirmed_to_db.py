"""
Run repeated-frame validation and save CONFIRMED events into PostgreSQL.

Uses custom UFM weights when available (ai/runs/train/ufm_custom/weights/best.pt),
otherwise pretrained COCO. Stores normalized UFM class names; maps to violation
types for auto-draft cases.

Usage (from project root, venv active):
  python ai/save_confirmed_to_db.py --source ai/samples/sample_exam_clip.mp4

Optional auto-draft:
  python ai/save_confirmed_to_db.py --source ai/samples/sample_exam_clip.mp4 ^
    --auto-draft --student-id 2 --exam-id 1 --reporter-id 1
"""

from __future__ import annotations

import argparse
import sys
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

from database import SessionLocal  # noqa: E402
from detection_bridge import (  # noqa: E402
    create_draft_case_from_detection,
    notify_detection_alert,
)
from evidence_auto import create_detection_evidence  # noqa: E402
from models.camera import Camera  # noqa: E402
from models.detection import Detection  # noqa: E402
from ufm_classes import (  # noqa: E402
    is_ufm_watchlist,
    normalize_label,
    resolve_weights,
    to_violation_type,
)


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description="Save confirmed detections to DB")
    parser.add_argument(
        "--source",
        type=str,
        default=str(root / "samples" / "sample_exam_clip.mp4"),
    )
    parser.add_argument(
        "--weights",
        type=str,
        default=None,
        help="Force weights (default: custom best.pt if present, else COCO)",
    )
    parser.add_argument("--conf", type=float, default=0.35)
    parser.add_argument("--min-frames", type=int, default=3)
    parser.add_argument("--camera-id", type=int, default=None)
    parser.add_argument(
        "--auto-draft",
        action="store_true",
        help="Create UFM case drafts for watchlist classes (needs student/exam/reporter)",
    )
    parser.add_argument("--student-id", type=int, default=None)
    parser.add_argument("--exam-id", type=int, default=None)
    parser.add_argument("--reporter-id", type=int, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source = Path(args.source)
    if not source.exists():
        raise FileNotFoundError(f"Source not found: {source}")

    if args.auto_draft and not all([args.student_id, args.exam_id, args.reporter_id]):
        raise SystemExit(
            "--auto-draft requires --student-id, --exam-id, and --reporter-id"
        )

    weights, mode = resolve_weights(args.weights)

    print("=" * 60)
    print("Save confirmed detections -> PostgreSQL")
    print(f"source={source}")
    print(f"weights={weights}")
    print(f"mode={mode}")
    print(f"auto_draft={args.auto_draft}")
    print("=" * 60)

    model = YOLO(str(weights))
    cap = cv2.VideoCapture(str(source))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {source}")

    streaks: dict[str, int] = defaultdict(int)
    confirmed_labels: set[str] = set()
    pending_rows: list[tuple[Detection, object]] = []

    frame_index = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break

        result = model.predict(frame, conf=args.conf, verbose=False)[0]
        names = result.names
        labels_this_frame: dict[str, float] = {}
        if result.boxes is not None:
            for box in result.boxes:
                cls_id = int(box.cls[0].item())
                conf = float(box.conf[0].item())
                raw = names.get(cls_id, str(cls_id))
                normalized = normalize_label(raw)
                labels_this_frame[normalized] = max(
                    labels_this_frame.get(normalized, 0.0), conf
                )

        active = set(labels_this_frame.keys())
        for label in list(streaks.keys()):
            if label not in active:
                streaks[label] = 0

        for label, conf in labels_this_frame.items():
            streaks[label] += 1
            if streaks[label] >= args.min_frames and label not in confirmed_labels:
                confirmed_labels.add(label)
                row = Detection(
                    camera_id=args.camera_id,
                    student_id=args.student_id,
                    detection_type=label,
                    confidence=conf,
                    timestamp=datetime.now(timezone.utc).replace(tzinfo=None),
                    is_confirmed=True,
                    source_path=str(source).replace("\\", "/"),
                    frame_index=frame_index,
                )
                pending_rows.append((row, frame.copy()))
                violation = to_violation_type(label)
                print(
                    f"CONFIRMED -> DB  {label}  violation={violation or '—'}  "
                    f"conf={conf:.3f}  frame={frame_index}"
                )

        frame_index += 1

    cap.release()

    db = SessionLocal()
    try:
        camera_id = args.camera_id
        if camera_id is not None and db.get(Camera, camera_id) is None:
            print(f"Warning: camera_id={camera_id} not found; saving with camera_id=NULL")
            camera_id = None
            for row, _frame in pending_rows:
                row.camera_id = None

        drafts_created = 0
        for row, snap_frame in pending_rows:
            db.add(row)
            db.flush()
            alert_count = notify_detection_alert(db, row)
            print(f"  alerted {alert_count} HOD user(s) for detection #{row.id}")
            create_detection_evidence(
                db,
                detection_id=int(row.id),
                camera_id=row.camera_id,
                confidence=row.confidence,
                frame_bgr=snap_frame,
                clip_frames=None,
                case_id=None,
            )
            print(f"  auto SNAPSHOT evidence for detection #{row.id}")

            if args.auto_draft and is_ufm_watchlist(row.detection_type):
                case = create_draft_case_from_detection(
                    db,
                    detection=row,
                    student_id=args.student_id,
                    exam_id=args.exam_id,
                    reported_by=args.reporter_id,
                )
                drafts_created += 1
                print(f"  DRAFT CASE {case.case_number} from detection #{row.id}")

        db.commit()
        print(f"Saved {len(pending_rows)} confirmed detection(s).")
        if args.auto_draft:
            print(f"Auto-drafts created: {drafts_created}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
