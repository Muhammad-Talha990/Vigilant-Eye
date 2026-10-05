"""
Seed ai/dataset/ufm from sample images + weak labels from pretrained COCO YOLO.

This creates a *starter* dataset so train_yolo.py can run. Labels are approximate
(COCO→UFM mapping). Replace with hand annotations for real accuracy.

Usage (from project root, venv active):
  python ai/seed_ufm_dataset.py
  python ai/seed_ufm_dataset.py --include-hard-negatives
  python ai/train_yolo.py --epochs 20 --batch 4
"""

from __future__ import annotations

import argparse
import random
import shutil
from pathlib import Path

from ultralytics import YOLO

from ufm_classes import AI_ROOT, UFM_CLASS_NAMES, default_coco_weights

# Sample images that are exam/UFM-ish (prefer these for training seed)
PREFERRED_SAMPLES = [
    "phone_closeup.jpg",
    "phone_on_desk.jpg",
    "phone_under_desk.jpg",
    "phone_in_lap.jpg",
    "smartwatch_closeup.jpg",
    "smartwatch.jpg",
    "exam_hall.jpg",
]

# Optional hard negatives (no UFM objects expected — empty labels)
HARD_NEGATIVES: list[str] = []

VIDEO_SAMPLE = "sample_exam_clip.mp4"

# COCO class name -> UFM class index in data.yaml
COCO_TO_UFM_INDEX = {
    "cell phone": 0,  # mobile_phone
    "book": 2,  # notes_paper
    "laptop": 3,  # electronic_gadget
    "keyboard": 3,
    "mouse": 3,
    "remote": 3,
    "suitcase": 4,  # suspicious_object
    "handbag": 4,
    "backpack": 4,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed UFM YOLO dataset from samples")
    parser.add_argument(
        "--samples",
        type=str,
        default=str(AI_ROOT / "samples"),
        help="Folder with source images",
    )
    parser.add_argument(
        "--dest",
        type=str,
        default=str(AI_ROOT / "dataset" / "ufm"),
        help="Dataset root (images/ + labels/)",
    )
    parser.add_argument(
        "--weights",
        type=str,
        default=str(default_coco_weights()),
        help="COCO weights used to auto-label",
    )
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--val-ratio", type=float, default=0.25)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--include-hard-negatives",
        action="store_true",
        help="Also copy bus/zidane as empty-label negatives",
    )
    parser.add_argument(
        "--from-video",
        action="store_true",
        help=f"Also extract frames from samples/{VIDEO_SAMPLE}",
    )
    parser.add_argument(
        "--video-every",
        type=int,
        default=8,
        help="Keep every Nth frame when --from-video",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing images/labels with same basename",
    )
    return parser.parse_args()


def extract_video_frames(
    video_path: Path, out_dir: Path, every: int
) -> list[Path]:
    import cv2

    out_dir.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"SKIP could not open video: {video_path}")
        return []
    saved: list[Path] = []
    idx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if idx % max(1, every) == 0:
            name = f"{video_path.stem}_f{idx:04d}.jpg"
            path = out_dir / name
            cv2.imwrite(str(path), frame)
            saved.append(path)
        idx += 1
    cap.release()
    return saved


def yolo_line(cls_id: int, xywhn) -> str:
    x, y, w, h = [float(v) for v in xywhn]
    return f"{cls_id} {x:.6f} {y:.6f} {w:.6f} {h:.6f}"


def auto_label(model: YOLO, image_path: Path, conf: float) -> list[str]:
    result = model.predict(str(image_path), conf=conf, verbose=False)[0]
    names = result.names
    lines: list[str] = []
    if result.boxes is None or len(result.boxes) == 0:
        return lines
    for box in result.boxes:
        cls_id = int(box.cls[0].item())
        coco_name = names.get(cls_id, "")
        ufm_id = COCO_TO_UFM_INDEX.get(coco_name)
        if ufm_id is None:
            continue
        # xywh normalized
        xywhn = box.xywhn[0].tolist()
        lines.append(yolo_line(ufm_id, xywhn))
    return lines


def main() -> None:
    args = parse_args()
    samples = Path(args.samples)
    dest = Path(args.dest)
    img_train = dest / "images" / "train"
    img_val = dest / "images" / "val"
    lbl_train = dest / "labels" / "train"
    lbl_val = dest / "labels" / "val"
    for d in (img_train, img_val, lbl_train, lbl_val):
        d.mkdir(parents=True, exist_ok=True)

    names = list(PREFERRED_SAMPLES)
    if args.include_hard_negatives:
        names.extend(HARD_NEGATIVES)

    files = []
    for name in names:
        path = samples / name
        if path.is_file():
            files.append(path)
        else:
            print(f"SKIP missing sample: {name}")

    if args.from_video:
        video = samples / VIDEO_SAMPLE
        frame_dir = AI_ROOT / "dataset" / "_extracted_frames"
        if video.is_file():
            extracted = extract_video_frames(video, frame_dir, args.video_every)
            print(f"Extracted {len(extracted)} frames from {VIDEO_SAMPLE}")
            files.extend(extracted)
        else:
            print(f"SKIP missing video: {VIDEO_SAMPLE}")

    if not files:
        raise SystemExit(f"No sample images found in {samples}")

    random.seed(args.seed)
    shuffled = files[:]
    random.shuffle(shuffled)
    val_count = max(1, int(len(shuffled) * args.val_ratio))
    if len(shuffled) == 1:
        val_count = 0  # keep single image in train
    val_set = set(shuffled[:val_count])

    print("=" * 60)
    print("Seed UFM dataset (weak COCO labels)")
    print(f"samples : {samples}")
    print(f"dest    : {dest}")
    print(f"images  : {len(files)}  (val={val_count})")
    print(f"classes : {UFM_CLASS_NAMES}")
    print("=" * 60)

    model = YOLO(args.weights)
    labeled = 0
    empty = 0

    for path in shuffled:
        split = "val" if path in val_set else "train"
        img_dir = img_val if split == "val" else img_train
        lbl_dir = lbl_val if split == "val" else lbl_train
        dest_img = img_dir / path.name
        dest_lbl = lbl_dir / f"{path.stem}.txt"

        if dest_img.exists() and not args.force:
            print(f"KEEP  {split}/{path.name} (exists, use --force to overwrite)")
            continue

        shutil.copy2(path, dest_img)
        if path.name in HARD_NEGATIVES:
            lines = []
        else:
            lines = auto_label(model, path, args.conf)

        dest_lbl.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        if lines:
            labeled += 1
            print(f"OK    {split}/{path.name}  boxes={len(lines)}")
        else:
            empty += 1
            print(f"EMPTY {split}/{path.name}  (no mapped COCO boxes — re-label manually)")

    print()
    print(f"Done. labeled={labeled}, empty={empty}")
    print("Next:")
    print("  1. Open images in LabelImg/CVAT and fix weak labels (especially watches).")
    print("  2. python ai/train_yolo.py --epochs 30 --batch 4")
    print("  3. python ai/test_detector.py --source ai/samples/phone_under_desk.jpg")


if __name__ == "__main__":
    main()
