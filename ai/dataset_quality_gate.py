"""
VigilantEye dataset quality GATE (no training).

Fails with exit code 2 when critical problems exist.

Checks a prepared YOLO root (images/ + labels/ + data.yaml) and/or a placed
raw export root.

Usage:
  python ai/dataset_quality_gate.py --prepared ai/dataset/ufm
  python ai/dataset_quality_gate.py --placed "C:/.../ai/dataset/ufm/dataset"
  python ai/dataset_quality_gate.py --prepared ai/dataset/ufm --require-min-labeled 500 --require-classes 0,2
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Dataset quality gate (fail on critical)")
    p.add_argument("--prepared", type=str, default="", help="YOLO root with images/labels")
    p.add_argument("--placed", type=str, default="", help="Raw placed export root")
    p.add_argument("--out", type=str, default="", help="JSON report path")
    p.add_argument("--require-min-labeled", type=int, default=1)
    p.add_argument(
        "--require-classes",
        type=str,
        default="",
        help="Comma-separated class ids that must have >=1 box",
    )
    p.add_argument("--max-empty-label-ratio", type=float, default=0.5)
    p.add_argument("--forbid-weak-only", action="store_true")
    p.add_argument(
        "--training-ready",
        action="store_true",
        help="Strict gate: train/val/test, taxonomy, license manifest, leakage heuristic",
    )
    p.add_argument(
        "--require-license-manifest",
        action="store_true",
        help="Require ai/dataset/LICENSE_MANIFEST.md (or --license-manifest path)",
    )
    p.add_argument(
        "--license-manifest",
        type=str,
        default="",
        help="Path to LICENSE_MANIFEST.md",
    )
    p.add_argument(
        "--expected-names",
        type=str,
        default="mobile_phone,smart_watch,normal_watch,notes_paper,electronic_gadget",
        help="Comma-separated expected class names in order (training-ready)",
    )
    return p.parse_args()


def _session_key(stem: str) -> str:
    import re

    s = stem
    s = re.sub(r"\.rf\.[a-fA-F0-9]+$", "", s)
    s = re.sub(r"(_jpg|_JPG|_png|_PNG|_jpeg|_JPEG)$", "", s)
    s = re.sub(r"([_-]frame[-_]?\d+)$", "", s, flags=re.I)
    s = re.sub(r"([_-]\d{3,6})$", "", s)
    return s or stem


def check_session_leakage(root: Path) -> dict:
    """Fail if the same session_key appears in more than one of train/val/test."""
    critical: list[str] = []
    warnings: list[str] = []
    by_split: dict[str, set[str]] = {}
    for split in ("train", "val", "test"):
        img_dir = root / "images" / split
        keys: set[str] = set()
        if img_dir.is_dir():
            for p in img_dir.iterdir():
                if p.suffix.lower() in IMG_EXTS:
                    keys.add(_session_key(p.stem))
        by_split[split] = keys
    splits = [s for s, keys in by_split.items() if keys]
    leaked = []
    for i, a in enumerate(splits):
        for b in splits[i + 1 :]:
            inter = by_split[a] & by_split[b]
            if inter:
                leaked.append(
                    {
                        "splits": [a, b],
                        "count": len(inter),
                        "sample": sorted(inter)[:5],
                    }
                )
    if leaked:
        critical.append(
            "session_key leakage across splits: "
            + ", ".join(f"{x['splits'][0]}/{x['splits'][1]}={x['count']}" for x in leaked)
        )
    return {
        "critical": critical,
        "warnings": warnings,
        "stats": {
            "keys_per_split": {k: len(v) for k, v in by_split.items()},
            "leakage": leaked,
        },
    }


def check_taxonomy(names: object, expected: list[str]) -> list[str]:
    critical: list[str] = []
    if isinstance(names, dict):
        ordered = [str(names[i]) if i in names else str(names.get(str(i), "")) for i in range(len(expected))]
    elif isinstance(names, list):
        ordered = [str(x) for x in names]
    else:
        return ["taxonomy names missing or unsupported type"]
    if ordered != expected:
        critical.append(
            f"taxonomy mismatch: got {ordered} expected {expected}"
        )
    return critical


def parse_label(path: Path) -> tuple[list[int], list[str]]:
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    ids: list[int] = []
    bad: list[str] = []
    if not text:
        return ids, ["empty"]
    for line in text.splitlines():
        parts = line.split()
        if len(parts) != 5:
            bad.append("field_count")
            continue
        try:
            cid = int(float(parts[0]))
            vals = [float(x) for x in parts[1:]]
        except ValueError:
            bad.append("parse")
            continue
        if any(v < 0 or v > 1 for v in vals) or vals[2] <= 0 or vals[3] <= 0:
            bad.append("geometry")
            continue
        ids.append(cid)
    return ids, bad


def check_prepared(root: Path) -> dict:
    critical: list[str] = []
    warnings: list[str] = []
    stats: dict = {"splits": {}}
    data_yaml = root / "data.yaml"
    names = {}
    if not data_yaml.is_file():
        critical.append("missing data.yaml")
    else:
        try:
            import yaml

            data = yaml.safe_load(data_yaml.read_text(encoding="utf-8")) or {}
            names = data.get("names") or {}
            stats["names"] = names
            # Detect garbage class names (README text leaked into names)
            if isinstance(names, dict):
                for k, v in names.items():
                    s = str(v)
                    if len(s) > 40 or "roboflow" in s.lower() or s.startswith("- "):
                        critical.append(f"corrupt class name for id {k}: {s[:60]}")
            elif isinstance(names, list):
                for i, v in enumerate(names):
                    s = str(v)
                    if len(s) > 40 or "roboflow" in s.lower() or s.startswith("- "):
                        critical.append(f"corrupt class name for id {i}: {s[:60]}")
        except Exception as exc:  # noqa: BLE001
            critical.append(f"data.yaml parse error: {exc}")

    total_labeled = 0
    total_images = 0
    total_boxes = 0
    empty_labels = 0
    bad_rows = 0
    class_boxes: Counter[int] = Counter()

    for split in ("train", "val", "test"):
        img_dir = root / "images" / split
        lab_dir = root / "labels" / split
        imgs = (
            [p for p in img_dir.iterdir() if p.suffix.lower() in IMG_EXTS]
            if img_dir.is_dir()
            else []
        )
        labs = list(lab_dir.glob("*.txt")) if lab_dir.is_dir() else []
        total_images += len(imgs)
        split_boxes = 0
        split_empty = 0
        for lab in labs:
            ids, bad = parse_label(lab)
            if "empty" in bad and not ids:
                empty_labels += 1
                split_empty += 1
                continue
            bad_rows += len([b for b in bad if b != "empty"])
            if ids:
                total_labeled += 1
            for cid in ids:
                class_boxes[cid] += 1
                split_boxes += 1
                total_boxes += 1
        # missing labels
        missing = 0
        for img in imgs:
            if not (lab_dir / f"{img.stem}.txt").is_file():
                missing += 1
        orphans = 0
        stems = {p.stem for p in imgs}
        for lab in labs:
            if lab.stem not in stems:
                orphans += 1
        stats["splits"][split] = {
            "images": len(imgs),
            "labels": len(labs),
            "boxes": split_boxes,
            "empty_labels": split_empty,
            "missing_labels": missing,
            "orphan_labels": orphans,
        }
        if missing and imgs:
            warnings.append(f"{split}: {missing} images missing label files")
        if orphans:
            warnings.append(f"{split}: {orphans} orphan label files")

    stats["totals"] = {
        "images": total_images,
        "labeled_nonempty": total_labeled,
        "boxes": total_boxes,
        "empty_labels": empty_labels,
        "bad_rows": bad_rows,
        "class_boxes": {str(k): v for k, v in sorted(class_boxes.items())},
    }
    if total_images == 0:
        critical.append("no images under prepared images/{train,val,test}")
    if total_labeled == 0:
        critical.append("no non-empty YOLO labels in prepared set")
    if total_images and empty_labels / max(1, sum(s["labels"] for s in stats["splits"].values())) > 0.99:
        # many empty files
        pass
    return {"critical": critical, "warnings": warnings, "stats": stats}


def check_placed(root: Path) -> dict:
    critical: list[str] = []
    warnings: list[str] = []
    imgs = [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in IMG_EXTS]
    vids = [
        p
        for p in root.rglob("*")
        if p.is_file() and p.suffix.lower() in {".mov", ".mp4", ".avi", ".mkv"}
    ]
    # label-like txt excluding readmes
    txts = [
        p
        for p in root.rglob("*.txt")
        if p.is_file() and "readme" not in p.name.lower()
    ]
    labeled = 0
    for img in imgs:
        if img.with_suffix(".txt").is_file():
            labeled += 1
            continue
        parts = list(img.parts)
        if "images" in parts:
            i = parts.index("images")
            alt = Path(*parts[:i], "labels", *parts[i + 1 :]).with_suffix(".txt")
            if alt.is_file():
                labeled += 1
    stats = {
        "images": len(imgs),
        "videos": len(vids),
        "label_like_txt": len(txts),
        "paired_labeled_images": labeled,
    }
    if imgs and labeled == 0:
        critical.append(
            f"placed root has {len(imgs)} images but 0 paired YOLO labels"
        )
    if vids and labeled == 0:
        warnings.append(
            f"{len(vids)} videos present with no object annotations"
        )
    return {"critical": critical, "warnings": warnings, "stats": stats}


def main() -> int:
    args = parse_args()
    ai_root = Path(__file__).resolve().parent
    report: dict = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "critical": [],
        "warnings": [],
        "prepared": None,
        "placed": None,
        "training_ready_checks": None,
        "gate_status": "UNKNOWN",
        "gate_pass": False,
    }
    if not args.prepared and not args.placed and not args.training_ready:
        print("Provide --prepared and/or --placed (or --training-ready with --prepared)", file=sys.stderr)
        return 2

    if args.training_ready and not args.prepared:
        # Default prepared root for training-ready mode
        args.prepared = str(ai_root / "dataset" / "ufm")
        args.require_license_manifest = True
        args.forbid_weak_only = True
        if not args.require_classes:
            args.require_classes = "0,1,2,3,4"
        if args.require_min_labeled < 200:
            args.require_min_labeled = 200

    if args.placed:
        placed = check_placed(Path(args.placed))
        report["placed"] = placed
        report["critical"].extend(placed["critical"])
        report["warnings"].extend(placed["warnings"])

    if args.prepared:
        prep_root = Path(args.prepared)
        prep = check_prepared(prep_root)
        report["prepared"] = prep
        report["critical"].extend(prep["critical"])
        report["warnings"].extend(prep["warnings"])
        totals = prep["stats"].get("totals", {})
        if totals.get("labeled_nonempty", 0) < args.require_min_labeled:
            report["critical"].append(
                f"labeled_nonempty {totals.get('labeled_nonempty')} < required {args.require_min_labeled}"
            )
        if args.require_classes:
            need = [int(x) for x in args.require_classes.split(",") if x.strip() != ""]
            cb = {int(k): v for k, v in (totals.get("class_boxes") or {}).items()}
            for cid in need:
                if cb.get(cid, 0) < 1:
                    report["critical"].append(f"required class id {cid} has 0 boxes")
        cb = {int(k): v for k, v in (totals.get("class_boxes") or {}).items()}
        boxes = sum(cb.values()) or 1
        phone = cb.get(0, 0)
        names_obj = prep["stats"].get("names") or {}
        name_list = (
            [str(names_obj.get(i, names_obj.get(str(i), ""))) for i in range(8)]
            if isinstance(names_obj, dict)
            else [str(x) for x in names_obj]
            if isinstance(names_obj, list)
            else []
        )
        has_suspicious = any("suspicious" in n.lower() for n in name_list)
        # Weak bootstrap used class "suspicious_object" heavily
        if args.forbid_weak_only or (args.training_ready and has_suspicious):
            sus_id = None
            for i, n in enumerate(name_list):
                if "suspicious" in n.lower():
                    sus_id = i
                    break
            sus = cb.get(sus_id, 0) if sus_id is not None else 0
            if phone < 20 and sus / boxes > 0.7:
                report["critical"].append(
                    "Label distribution looks like COCO weak-label bootstrap "
                    "(very few phones, suspicious_* dominant) — unsuitable for final FYP training"
                )

        if args.training_ready:
            tr: dict = {"checks": []}
            splits = prep["stats"].get("splits") or {}
            for req in ("train", "val", "test"):
                nimg = (splits.get(req) or {}).get("images", 0)
                tr["checks"].append({req: nimg})
                if nimg < 1:
                    report["critical"].append(f"training-ready: images/{req} is empty")
            expected = [x.strip() for x in args.expected_names.split(",") if x.strip()]
            report["critical"].extend(
                check_taxonomy(prep["stats"].get("names"), expected)
            )
            leak = check_session_leakage(prep_root)
            report["critical"].extend(leak["critical"])
            report["warnings"].extend(leak["warnings"])
            tr["leakage"] = leak["stats"]
            # mapping module must import
            try:
                sys.path.insert(0, str(ai_root))
                import dataset_mapping as dm  # noqa: WPS433

                tr["mapping_includes"] = sorted(
                    f"{a}::{b}->{c}" for (a, b), c in dm.included_source_to_ve().items()
                )
            except Exception as exc:  # noqa: BLE001
                report["critical"].append(f"dataset_mapping import failed: {exc}")
            report["training_ready_checks"] = tr

    if args.require_license_manifest or args.training_ready:
        man = (
            Path(args.license_manifest)
            if args.license_manifest
            else ai_root / "dataset" / "LICENSE_MANIFEST.md"
        )
        if not man.is_file():
            report["critical"].append(f"missing license manifest: {man}")
        else:
            text = man.read_text(encoding="utf-8", errors="replace")
            if "CC BY 4.0" not in text and "NOT VERIFIED" not in text:
                report["warnings"].append(
                    "license manifest present but contains no CC BY / NOT VERIFIED markers"
                )

    if report["critical"]:
        report["gate_status"] = "FAIL"
        report["gate_pass"] = False
        code = 2
    elif report["warnings"]:
        report["gate_status"] = "PASS_WITH_WARNINGS"
        report["gate_pass"] = True
        code = 1
    else:
        report["gate_status"] = "PASS"
        report["gate_pass"] = True
        code = 0

    out = (
        Path(args.out)
        if args.out
        else Path(__file__).resolve().parent
        / "runs"
        / "forensics"
        / "quality_gate.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"GATE: {report['gate_status']} pass={report['gate_pass']}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
