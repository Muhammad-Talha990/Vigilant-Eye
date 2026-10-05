"""
VigilantEye — YOLO detector (custom UFM weights preferred, COCO fallback).

Usage (from project root, with backend venv active):
  cd "D:\\BS CS\\Vigilant Eye"
  .\\backend\\venv\\Scripts\\Activate.ps1
  python ai/test_detector.py --source ai/samples/phone_under_desk.jpg

Weight selection (automatic unless --weights given):
  1. ai/runs/train/ufm_custom/weights/best.pt  (after train_yolo.py)
  2. ai/weights/yolov8n.pt                     (pretrained COCO PoC)
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from ultralytics import YOLO

from ufm_classes import is_ufm_watchlist, normalize_label, resolve_weights, to_violation_type


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description="VigilantEye YOLO detector")
    parser.add_argument(
        "--source",
        type=str,
        default=str(root / "samples" / "bus.jpg"),
        help="Path to image or video",
    )
    parser.add_argument(
        "--weights",
        type=str,
        default=None,
        help="Force a weights file (default: custom best.pt if present, else COCO)",
    )
    parser.add_argument(
        "--conf",
        type=float,
        default=0.25,
        help="Confidence threshold",
    )
    parser.add_argument(
        "--outdir",
        type=str,
        default=str(root / "outputs"),
        help="Folder for annotated outputs",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source = Path(args.source)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    if not source.exists():
        raise FileNotFoundError(f"Source not found: {source}")

    weights, mode = resolve_weights(args.weights)

    print("=" * 60)
    print("VigilantEye YOLO detector")
    print(f"time     : {datetime.now(timezone.utc).isoformat()}")
    print(f"source   : {source}")
    print(f"weights  : {weights}")
    print(f"mode     : {mode}")
    print(f"conf     : {args.conf}")
    print("=" * 60)
    if mode == "coco":
        print(
            "NOTE: Using pretrained COCO weights (no custom best.pt yet). "
            "Train with: python ai/train_yolo.py"
        )
    elif mode == "custom":
        print("Using custom UFM-trained weights.")
    print()

    model = YOLO(str(weights))
    results = model.predict(
        source=str(source),
        conf=args.conf,
        save=False,
        verbose=False,
    )

    total = 0
    ufm_hits = 0
    for i, result in enumerate(results):
        names = result.names
        boxes = result.boxes
        print(f"--- frame/image {i} ---")
        if boxes is None or len(boxes) == 0:
            print("No detections above confidence threshold.")
        else:
            for box in boxes:
                cls_id = int(box.cls[0].item())
                conf = float(box.conf[0].item())
                raw = names.get(cls_id, str(cls_id))
                normalized = normalize_label(raw)
                violation = to_violation_type(raw)
                watch = is_ufm_watchlist(raw)
                total += 1
                if watch:
                    ufm_hits += 1
                print(
                    f"  class={raw:18} -> {normalized:18} "
                    f"violation={violation or '—':18} "
                    f"conf={conf:.3f}"
                    f"{'  [UFM]' if watch else ''}"
                )

        stem = source.stem
        out_path = outdir / f"{stem}_annotated_{i}.jpg"
        result.save(filename=str(out_path))
        print(f"Annotated output: {out_path}")

    print()
    print(f"Total detections: {total}  (UFM-mapped: {ufm_hits})")
    print("Done.")


if __name__ == "__main__":
    main()
