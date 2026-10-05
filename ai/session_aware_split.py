"""
Session/video-aware train/val/test split for VigilantEye UFM datasets.

CRITICAL: Do NOT randomly split individual frames from the same video into
train and test — near-identical frames leak and inflate mAP.

This tool groups images by a session key derived from filename prefixes
(Roboflow / video stem patterns) and assigns whole sessions to one split.

Usage:
  python ai/session_aware_split.py --dry-run
  python ai/session_aware_split.py --apply --val-ratio 0.12 --test-ratio 0.08

Does not invent labels. Requires existing images/ + labels/ under dataset root.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_DS = ROOT / "dataset" / "ufm"


def session_key(stem: str) -> str:
    """
    Derive a stable session/video id from a filename stem.

    Heuristics (conservative):
    - strip Roboflow augmentation suffixes (.rf.<hash>)
    - strip trailing frame indices (_0000, -12, frame123)
    - keep leading video / clip identity
    """
    s = stem
    s = re.sub(r"\.rf\.[a-fA-F0-9]+$", "", s)
    s = re.sub(r"(_jpg|_JPG|_png|_PNG|_jpeg|_JPEG)$", "", s)
    s = re.sub(r"([_-]frame[-_]?\d+)$", "", s, flags=re.I)
    s = re.sub(r"([_-]\d{3,6})$", "", s)
    s = re.sub(r"(-\d+)$", "", s)
    return s or stem


def collect_pairs(images_dir: Path, labels_dir: Path) -> list[tuple[Path, Path | None, str]]:
    pairs: list[tuple[Path, Path | None, str]] = []
    if not images_dir.is_dir():
        return pairs
    for img in sorted(images_dir.iterdir()):
        if img.suffix.lower() not in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}:
            continue
        lab = labels_dir / f"{img.stem}.txt"
        pairs.append((img, lab if lab.is_file() else None, session_key(img.stem)))
    return pairs


def assign_sessions(
    sessions: list[str],
    *,
    val_ratio: float,
    test_ratio: float,
    seed: int,
) -> dict[str, str]:
    rng = random.Random(seed)
    ordered = list(sessions)
    rng.shuffle(ordered)
    n = len(ordered)
    n_test = int(round(n * test_ratio))
    n_val = int(round(n * val_ratio))
    mapping: dict[str, str] = {}
    for i, sid in enumerate(ordered):
        if i < n_test:
            mapping[sid] = "test"
        elif i < n_test + n_val:
            mapping[sid] = "val"
        else:
            mapping[sid] = "train"
    return mapping


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Session-aware YOLO split")
    p.add_argument("--dataset", type=str, default=str(DEFAULT_DS))
    p.add_argument("--val-ratio", type=float, default=0.12)
    p.add_argument("--test-ratio", type=float, default=0.08)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--dry-run", action="store_true", help="Report only; do not move files")
    p.add_argument("--apply", action="store_true", help="Rewrite images/{train,val,test}")
    p.add_argument(
        "--source-split",
        type=str,
        default="train",
        help="Which existing split folder to re-pool (default: train). "
        "Use 'all' to pool train+val (+test if present).",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    ds = Path(args.dataset)
    images_root = ds / "images"
    labels_root = ds / "labels"

    pools = ["train", "val", "test"] if args.source_split == "all" else [args.source_split]
    pairs: list[tuple[Path, Path | None, str]] = []
    for split in pools:
        pairs.extend(collect_pairs(images_root / split, labels_root / split))

    by_session: dict[str, list[tuple[Path, Path | None]]] = defaultdict(list)
    for img, lab, sid in pairs:
        by_session[sid].append((img, lab))

    mapping = assign_sessions(
        list(by_session.keys()),
        val_ratio=args.val_ratio,
        test_ratio=args.test_ratio,
        seed=args.seed,
    )

    counts = {"train": 0, "val": 0, "test": 0}
    sess_counts = {"train": 0, "val": 0, "test": 0}
    for sid, items in by_session.items():
        dest = mapping[sid]
        counts[dest] += len(items)
        sess_counts[dest] += 1

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset": str(ds.resolve()),
        "seed": args.seed,
        "val_ratio": args.val_ratio,
        "test_ratio": args.test_ratio,
        "sessions_total": len(by_session),
        "sessions_per_split": sess_counts,
        "images_per_split": counts,
        "mode": "apply" if args.apply and not args.dry_run else "dry-run",
        "note": (
            "Whole sessions assigned to one split to reduce near-duplicate "
            "frame leakage. Filename heuristics are imperfect for some Roboflow "
            "exports — review session_key samples before claiming zero leakage."
        ),
    }

    outdir = ROOT / "runs"
    outdir.mkdir(parents=True, exist_ok=True)
    report_path = outdir / "session_aware_split_plan.json"
    # Sample of session keys for audit
    sample_keys = sorted(by_session.keys())[:40]
    report["sample_session_keys"] = sample_keys
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))

    if args.dry_run or not args.apply:
        print(f"\nPlan written to {report_path} (no files moved). Pass --apply to rewrite.")
        return 0

    # Rebuild under staging then swap
    staging = ds / "_split_staging"
    if staging.exists():
        shutil.rmtree(staging)
    for split in ("train", "val", "test"):
        (staging / "images" / split).mkdir(parents=True, exist_ok=True)
        (staging / "labels" / split).mkdir(parents=True, exist_ok=True)

    for sid, items in by_session.items():
        dest = mapping[sid]
        for img, lab in items:
            shutil.copy2(img, staging / "images" / dest / img.name)
            if lab is not None:
                shutil.copy2(lab, staging / "labels" / dest / lab.name)
            else:
                (staging / "labels" / dest / f"{img.stem}.txt").write_text("", encoding="utf-8")

    # Backup fingerprint
    fp = hashlib.sha1(json.dumps(report, sort_keys=True).encode()).hexdigest()[:12]
    backup = ds / f"_split_backup_{fp}"
    if (images_root).exists():
        if backup.exists():
            shutil.rmtree(backup)
        backup.mkdir(parents=True)
        shutil.move(str(images_root), str(backup / "images"))
        if labels_root.exists():
            shutil.move(str(labels_root), str(backup / "labels"))

    shutil.move(str(staging / "images"), str(images_root))
    shutil.move(str(staging / "labels"), str(labels_root))
    shutil.rmtree(staging, ignore_errors=True)

    report["backup"] = str(backup)
    report["applied"] = True
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Applied. Backup at {backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
