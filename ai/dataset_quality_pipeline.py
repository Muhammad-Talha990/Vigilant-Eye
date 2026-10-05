"""
Dataset quality checks for VigilantEye UFM YOLO data.

Covers: missing pairs, empty labels, corrupt images, class histogram,
source-aware split warnings. Does NOT invent annotations.

Usage:
  python ai/dataset_quality_pipeline.py
  python ai/dataset_quality_pipeline.py --report ai/runs/dataset_quality.json
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, UnidentifiedImageError

ROOT = Path(__file__).resolve().parent
UFM = ROOT / "dataset" / "ufm"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="UFM dataset quality pipeline")
    p.add_argument("--root", type=str, default=str(UFM))
    p.add_argument(
        "--report",
        type=str,
        default=str(ROOT / "runs" / "dataset_quality.json"),
    )
    return p.parse_args()


def _scan_split(base: Path, split: str) -> dict:
    img_dir = base / "images" / split
    lab_dir = base / "labels" / split
    images = sorted(img_dir.glob("*")) if img_dir.is_dir() else []
    images = [p for p in images if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}]
    labels = {p.stem: p for p in lab_dir.glob("*.txt")} if lab_dir.is_dir() else {}

    missing_labels = []
    empty_labels = []
    corrupt = []
    class_hist: Counter[int] = Counter()
    bad_lines = 0

    for img in images:
        lab = labels.get(img.stem)
        if lab is None:
            missing_labels.append(img.name)
            continue
        text = lab.read_text(encoding="utf-8", errors="replace").strip()
        if not text:
            empty_labels.append(img.name)
            continue
        for line in text.splitlines():
            parts = line.split()
            if len(parts) != 5:
                bad_lines += 1
                continue
            try:
                cid = int(float(parts[0]))
                coords = [float(x) for x in parts[1:]]
            except ValueError:
                bad_lines += 1
                continue
            if any(c < 0 or c > 1 for c in coords):
                bad_lines += 1
            class_hist[cid] += 1
        try:
            with Image.open(img) as im:
                im.verify()
        except (UnidentifiedImageError, OSError):
            corrupt.append(img.name)

    orphan_labels = [s for s in labels if s not in {p.stem for p in images}]
    return {
        "images": len(images),
        "labels": len(labels),
        "missing_labels": len(missing_labels),
        "empty_labels": len(empty_labels),
        "corrupt_images": len(corrupt),
        "orphan_labels": len(orphan_labels),
        "bad_label_lines": bad_lines,
        "class_histogram": {str(k): v for k, v in sorted(class_hist.items())},
        "samples_missing_labels": missing_labels[:10],
        "samples_corrupt": corrupt[:10],
    }


def main() -> int:
    args = parse_args()
    base = Path(args.root)
    data_yaml = base / "data.yaml"
    names = {}
    if data_yaml.is_file():
        import yaml

        data = yaml.safe_load(data_yaml.read_text(encoding="utf-8")) or {}
        names = data.get("names") or {}

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_root": str(base.resolve()),
        "class_names": names,
        "dataset_version_note": (
            "Merged Roboflow exports under dataset/ufm/dataset/ into images/{train,val}. "
            "Frame-level random splits from the same video can leak — prefer session-aware splits."
        ),
        "splits": {},
        "source_exports_present": [],
        "leakage_warning": (
            "If train/val frames were randomly split from the same video sessions, "
            "validation metrics may be optimistic. Re-split by video/session ID before "
            "claiming production accuracy."
        ),
        "custom_data_required": True,
        "privacy_note": (
            "Do not use real identifiable student CCTV without legal/ethical authorization. "
            "Prefer staged/authorized capture or public datasets with compatible licenses."
        ),
    }

    for split in ("train", "val", "test"):
        if (base / "images" / split).is_dir() or (base / "labels" / split).is_dir():
            report["splits"][split] = _scan_split(base, split)

    export_root = base / "dataset"
    if export_root.is_dir():
        report["source_exports_present"] = sorted(
            p.name for p in export_root.iterdir() if p.is_dir()
        )

    out = Path(args.report)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
