"""
Import a Roboflow YOLOv8 export into VigilantEye training layout.

Maps source class names -> UFM classes used by the portal / detector.

Usage:
  python ai/import_roboflow_dataset.py \\
    --source "ai/dataset/ufm/dataset/offline-exam-monitoring-4"
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import yaml

# Source label (lowercase) -> VigilantEye UFM class
DEFAULT_CLASS_MAP = {
    "phone": "mobile_phone",
    "cellphone": "mobile_phone",
    "cell phone": "mobile_phone",
    "mobile": "mobile_phone",
    "mobile phone": "mobile_phone",
    "handphone": "mobile_phone",
    "cheating-paper": "notes_paper",
    "cheating_paper": "notes_paper",
    "paper": "notes_paper",
    "book": "notes_paper",
    "notes": "notes_paper",
    "smartwatch": "smart_watch",
    "smart-watch": "smart_watch",
    "smart watch": "smart_watch",
    "wrist watch": "smart_watch",
    "wrist-watch": "smart_watch",
    "wristwatch": "smart_watch",
    "watch": "smart_watch",
    "cheating": "suspicious_object",
    "student cheating": "suspicious_object",
    "calculator": "electronic_gadget",
    "laptop": "electronic_gadget",
    "earphone": "electronic_gadget",
    "headphone": "electronic_gadget",
    "headphones": "electronic_gadget",
}

# Classes we keep but do not map to UFM portal types (still trainable)
KEEP_AS_IS = {
    "non-cheating": "non_cheating",
    "non_cheating": "non_cheating",
    "hand-normalmove": "hand_normal",
    "hand_normalmove": "hand_normal",
    "person": "person",
}

UFM_ORDER = [
    "mobile_phone",
    "smart_watch",
    "notes_paper",
    "electronic_gadget",
    "suspicious_object",
    "non_cheating",
    "hand_normal",
    "person",
]


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parent
    p = argparse.ArgumentParser(description="Import Roboflow YOLO export")
    p.add_argument(
        "--source",
        type=str,
        required=True,
        help="Folder containing data.yaml + train/valid(/test)",
    )
    p.add_argument(
        "--dest",
        type=str,
        default=str(root / "dataset" / "ufm"),
        help="VigilantEye dataset root (images/ + labels/)",
    )
    p.add_argument(
        "--ufm-only",
        action="store_true",
        help="Drop non-UFM classes (person/non_cheating/hand_normal)",
    )
    p.add_argument(
        "--merge",
        action="store_true",
        help="Append into existing dest (do not wipe). Prefixes filenames.",
    )
    p.add_argument(
        "--prefix",
        type=str,
        default="sw",
        help="Filename prefix when using --merge (default: sw)",
    )
    return p.parse_args()


def find_data_yaml(source: Path) -> Path:
    direct = source / "data.yaml"
    if direct.is_file():
        return direct
    matches = list(source.rglob("data.yaml"))
    if not matches:
        raise SystemExit(f"No data.yaml under {source}")
    # Prefer shallowest
    matches.sort(key=lambda p: len(p.parts))
    return matches[0]


def load_names(data: dict) -> list[str]:
    names = data.get("names")
    if isinstance(names, dict):
        return [names[k] for k in sorted(names, key=lambda x: int(x))]
    if isinstance(names, list):
        return list(names)
    raise SystemExit("data.yaml has no usable names list")


def resolve_split_dirs(base: Path, data: dict) -> dict[str, Path]:
    """Return mapping train/val(/test) -> images directory."""
    out: dict[str, Path] = {}
    for key, alias in (("train", "train"), ("val", "val"), ("valid", "val"), ("test", "test")):
        rel = data.get(key)
        if not rel:
            continue
        # Roboflow often uses ../train/images relative to a nested yaml
        cand = (base / rel).resolve()
        if cand.is_dir():
            out[alias] = cand
            continue
        # Fallback common layouts
        for guess in (
            base / alias / "images",
            base / ("valid" if alias == "val" else alias) / "images",
            base / "images" / alias,
        ):
            if guess.is_dir():
                out[alias] = guess.resolve()
                break
    if "train" not in out or "val" not in out:
        # Scan
        for split, alias in (("train", "train"), ("valid", "val"), ("val", "val")):
            img = base / split / "images"
            if img.is_dir():
                out[alias] = img.resolve()
    if "train" not in out or "val" not in out:
        raise SystemExit(f"Could not locate train/val image folders under {base}")
    return out


def labels_dir_for_images(images_dir: Path) -> Path:
    if images_dir.name == "images":
        return images_dir.parent / "labels"
    # sibling labels/
    sibling = images_dir.parent / "labels" / images_dir.name
    if sibling.is_dir():
        return sibling
    return images_dir.parent / "labels"


def map_class_name(raw: str) -> str | None:
    key = (raw or "").strip().lower()
    if key in DEFAULT_CLASS_MAP:
        return DEFAULT_CLASS_MAP[key]
    if key in KEEP_AS_IS:
        return KEEP_AS_IS[key]
    return None


def main() -> None:
    args = parse_args()
    source = Path(args.source).resolve()
    dest = Path(args.dest).resolve()
    yaml_path = find_data_yaml(source)
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
    base = yaml_path.parent
    src_names = load_names(data)
    print(f"Source yaml: {yaml_path}")
    print(f"Source classes ({len(src_names)}): {src_names}")

    existing_names: list[str] = []
    dest_yaml = dest / "data.yaml"
    if args.merge and dest_yaml.is_file():
        existing = yaml.safe_load(dest_yaml.read_text(encoding="utf-8")) or {}
        existing_names = load_names(existing)
        print(f"Merge into existing classes: {existing_names}")

    # Build old_id -> target class name
    old_to_target: dict[int, str] = {}
    dropped: list[str] = []
    for old_id, raw in enumerate(src_names):
        mapped = map_class_name(raw)
        if mapped is None:
            dropped.append(raw)
            continue
        if args.ufm_only and mapped not in {
            "mobile_phone",
            "smart_watch",
            "notes_paper",
            "electronic_gadget",
            "suspicious_object",
        }:
            dropped.append(raw)
            continue
        old_to_target[old_id] = mapped

    if args.merge and existing_names:
        final_names = list(existing_names)
        for name in old_to_target.values():
            if name not in final_names:
                final_names.append(name)
        # Prefer UFM order while keeping any extras
        preferred = [c for c in UFM_ORDER if c in final_names]
        rest = [c for c in final_names if c not in preferred]
        final_names = preferred + rest
    else:
        used = list(dict.fromkeys(old_to_target.values()))
        preferred = [c for c in UFM_ORDER if c in used]
        rest = [c for c in used if c not in preferred]
        final_names = preferred + rest

    old_to_final = {
        oid: final_names.index(name) for oid, name in old_to_target.items()
    }

    print(f"Mapped classes: {final_names}")
    if dropped:
        print(f"Dropped unmapped: {dropped}")

    splits = resolve_split_dirs(base, data)
    print(f"Splits: { {k: str(v) for k,v in splits.items()} }")

    for split in ("train", "val"):
        (dest / "images" / split).mkdir(parents=True, exist_ok=True)
        (dest / "labels" / split).mkdir(parents=True, exist_ok=True)
        if not args.merge:
            for p in (dest / "images" / split).glob("*"):
                if p.is_file():
                    p.unlink()
            for p in (dest / "labels" / split).glob("*"):
                if p.is_file():
                    p.unlink()

    copied = 0
    labeled = 0
    prefix = (args.prefix.strip() + "_") if args.merge else ""
    for alias, images_dir in splits.items():
        if alias == "test":
            continue
        split = "val" if alias == "val" else "train"
        labels_dir = labels_dir_for_images(images_dir)
        dest_img = dest / "images" / split
        dest_lbl = dest / "labels" / split

        for img in images_dir.iterdir():
            if not img.is_file() or img.suffix.lower() not in {
                ".jpg",
                ".jpeg",
                ".png",
                ".webp",
            }:
                continue
            lbl = labels_dir / f"{img.stem}.txt"
            new_lines: list[str] = []
            if lbl.is_file():
                for line in lbl.read_text(encoding="utf-8").splitlines():
                    parts = line.strip().split()
                    if len(parts) < 5:
                        continue
                    old_id = int(float(parts[0]))
                    if old_id not in old_to_final:
                        continue
                    parts[0] = str(old_to_final[old_id])
                    new_lines.append(" ".join(parts))

            if not new_lines and args.ufm_only:
                continue

            out_name = f"{prefix}{img.name}"
            out_stem = Path(out_name).stem
            shutil.copy2(img, dest_img / out_name)
            copied += 1
            (dest_lbl / f"{out_stem}.txt").write_text(
                ("\n".join(new_lines) + ("\n" if new_lines else "")),
                encoding="utf-8",
            )
            if new_lines:
                labeled += 1

    # If merge and we reordered class indices vs previous yaml, rewrite ALL dest labels
    if args.merge and existing_names and existing_names != final_names:
        old_name_to_idx = {n: i for i, n in enumerate(existing_names)}
        new_name_to_idx = {n: i for i, n in enumerate(final_names)}
        if set(existing_names) != set(final_names) or any(
            old_name_to_idx[n] != new_name_to_idx[n] for n in existing_names
        ):
            print("Reindexing existing labels to new class order...")
            for split in ("train", "val"):
                for lbl in (dest / "labels" / split).glob("*.txt"):
                    # Skip files we just wrote with new indices (prefixed)
                    if prefix and lbl.name.startswith(prefix):
                        continue
                    lines_out: list[str] = []
                    for line in lbl.read_text(encoding="utf-8").splitlines():
                        parts = line.strip().split()
                        if len(parts) < 5:
                            continue
                        old_id = int(float(parts[0]))
                        if old_id >= len(existing_names):
                            continue
                        name = existing_names[old_id]
                        parts[0] = str(new_name_to_idx[name])
                        lines_out.append(" ".join(parts))
                    lbl.write_text(
                        ("\n".join(lines_out) + ("\n" if lines_out else "")),
                        encoding="utf-8",
                    )

    out_yaml = {
        "path": ".",
        "train": "images/train",
        "val": "images/val",
        "names": {i: n for i, n in enumerate(final_names)},
    }
    yaml_out = dest / "data.yaml"
    yaml_out.write_text(
        "# VigilantEye UFM dataset (imported from Roboflow)\n"
        + yaml.safe_dump(out_yaml, sort_keys=False),
        encoding="utf-8",
    )

    print()
    print(f"Copied images: {copied} (with boxes: {labeled})")
    print(f"Wrote {yaml_out}")
    print("Next: python ai/train_yolo.py --epochs 50 --batch 4")


if __name__ == "__main__":
    main()
