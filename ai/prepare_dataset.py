"""Split raw images into train/val folders for YOLO (scaffold).

Usage:
  python ai/prepare_dataset.py --source ai/samples/raw_frames --val-ratio 0.2

Copies images into dataset/ufm/images/train|val. You still must add labels
in labels/train|val manually or via your annotation tool.
"""

from __future__ import annotations

import argparse
import random
import shutil
from pathlib import Path


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description="Split images for UFM YOLO dataset")
    parser.add_argument(
        "--source",
        type=str,
        required=True,
        help="Folder of raw .jpg/.png frames",
    )
    parser.add_argument(
        "--dest",
        type=str,
        default=str(root / "dataset" / "ufm" / "images"),
        help="Dataset images root (train/ and val/ subdirs created)",
    )
    parser.add_argument(
        "--val-ratio",
        type=float,
        default=0.2,
        help="Fraction for validation split",
    )
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source = Path(args.source)
    dest = Path(args.dest)
    train_dir = dest / "train"
    val_dir = dest / "val"
    train_dir.mkdir(parents=True, exist_ok=True)
    val_dir.mkdir(parents=True, exist_ok=True)

    exts = {".jpg", ".jpeg", ".png", ".webp"}
    files = sorted(
        p for p in source.iterdir() if p.is_file() and p.suffix.lower() in exts
    )
    if not files:
        raise SystemExit(f"No images found in {source}")

    random.seed(args.seed)
    random.shuffle(files)
    val_count = max(1, int(len(files) * args.val_ratio))
    val_set = set(files[:val_count])

    for path in files:
        target = val_dir if path in val_set else train_dir
        shutil.copy2(path, target / path.name)

    print(f"Copied {len(files) - len(val_set)} -> {train_dir}")
    print(f"Copied {len(val_set)} -> {val_dir}")
    print("Next: annotate and place .txt labels in dataset/ufm/labels/train|val")


if __name__ == "__main__":
    main()
