"""
VigilantEye — repeated-frame validation.

Confirms a class only if it appears in N consecutive frames above confidence.

Usage:
  python ai/validate_detector.py --source ai/samples/sample_exam_clip.mp4
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import cv2
from ultralytics import YOLO

from ufm_classes import normalize_label, resolve_weights, to_violation_type


@dataclass
class ConfirmedEvent:
    label: str
    normalized: str
    violation_type: str | None
    confidence: float
    frame_index: int
    timestamp_sec: float


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description="Repeated-frame YOLO validation")
    parser.add_argument(
        "--source",
        type=str,
        default=str(root / "samples" / "sample_exam_clip.mp4"),
        help="Path to video",
    )
    parser.add_argument(
        "--weights",
        type=str,
        default=None,
        help="Force weights (default: custom best.pt if present, else COCO)",
    )
    parser.add_argument("--conf", type=float, default=0.35)
    parser.add_argument(
        "--min-frames",
        type=int,
        default=3,
        help="Consecutive frames required to confirm a class",
    )
    parser.add_argument(
        "--outdir",
        type=str,
        default=str(root / "outputs"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source = Path(args.source)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    if not source.exists():
        raise FileNotFoundError(
            f"Source not found: {source}\n"
            "Run: python ai/make_sample_video.py"
        )

    weights, mode = resolve_weights(args.weights)

    print("=" * 60)
    print("VigilantEye repeated-frame validation")
    print(f"time       : {datetime.now(timezone.utc).isoformat()}")
    print(f"source     : {source}")
    print(f"weights    : {weights}")
    print(f"mode       : {mode}")
    print(f"conf       : {args.conf}")
    print(f"min_frames : {args.min_frames}")
    print("=" * 60)

    model = YOLO(str(weights))
    cap = cv2.VideoCapture(str(source))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {source}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 5.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    out_path = outdir / f"{source.stem}_validated.mp4"
    writer = cv2.VideoWriter(
        str(out_path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height),
    )

    streaks: dict[str, int] = defaultdict(int)
    confirmed_labels: set[str] = set()
    events: list[ConfirmedEvent] = []

    frame_index = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break

        results = model.predict(frame, conf=args.conf, verbose=False)
        result = results[0]
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
                event = ConfirmedEvent(
                    label=label,
                    normalized=label,
                    violation_type=to_violation_type(label),
                    confidence=conf,
                    frame_index=frame_index,
                    timestamp_sec=frame_index / fps,
                )
                events.append(event)
                print(
                    f"CONFIRMED  class={label:16} "
                    f"violation={event.violation_type or '—':16} "
                    f"conf={conf:.3f}  frame={frame_index}  "
                    f"t={event.timestamp_sec:.2f}s  "
                    f"(seen {streaks[label]} consecutive frames)"
                )

        annotated = result.plot()
        if events:
            latest = events[-1]
            banner = latest.label
            if latest.violation_type:
                banner = f"{latest.label} / {latest.violation_type}"
            cv2.putText(
                annotated,
                f"CONFIRMED: {banner} ({latest.confidence:.2f})",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 0),
                2,
                cv2.LINE_AA,
            )
        writer.write(annotated)
        frame_index += 1

    cap.release()
    writer.release()

    print()
    print(f"Frames processed : {frame_index}")
    print(f"Confirmed events : {len(events)}")
    for e in events:
        print(
            f"  - {e.label} -> {e.violation_type or 'unmapped'} "
            f"conf={e.confidence:.3f} @ frame {e.frame_index} ({e.timestamp_sec:.2f}s)"
        )
    print(f"Annotated video  : {out_path}")
    print("Done.")


if __name__ == "__main__":
    main()
