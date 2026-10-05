"""
AI-4 Annotation QA — automated validation + visual sampling (NO TRAINING).

Usage:
  python ai/annotation_qa.py
  python ai/annotation_qa.py --candidates ai/annotation/candidates/annotation_candidates.json
  python ai/annotation_qa.py --fail-on-incomplete
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
VALID_CLASS_IDS = {0, 1, 2, 3, 4}
CLASS_NAMES = {
    0: "mobile_phone",
    1: "smart_watch",
    2: "normal_watch",
    3: "notes_paper",
    4: "electronic_gadget",
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Annotation QA for VigilantEye candidates")
    p.add_argument(
        "--candidates",
        type=str,
        default=str(
            Path(__file__).resolve().parent
            / "annotation"
            / "candidates"
            / "annotation_candidates.json"
        ),
    )
    p.add_argument(
        "--label-roots",
        type=str,
        default="",
        help="Extra dirs to search for YOLO txt (comma-separated)",
    )
    p.add_argument(
        "--out",
        type=str,
        default=str(Path(__file__).resolve().parent / "runs" / "dataset_gate"),
    )
    p.add_argument("--visual-per-class", type=int, default=8)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--fail-on-incomplete", action="store_true")
    p.add_argument("--hash-max", type=int, default=2000)
    return p.parse_args()


def session_key(stem: str) -> str:
    s = stem
    s = re.sub(r"\.rf\.[a-fA-F0-9]+$", "", s)
    s = re.sub(r"(_jpg|_JPG|_png|_PNG|_jpeg|_JPEG)$", "", s)
    s = re.sub(r"([_-]frame[-_]?\d+)$", "", s, flags=re.I)
    s = re.sub(r"([_-]\d{3,6})$", "", s)
    return s or stem


def find_label(img: Path, extra_roots: list[Path]) -> Path | None:
    cands = [img.with_suffix(".txt")]
    for root in extra_roots:
        cands.append(root / f"{img.stem}.txt")
        cands.append(root / "labels" / f"{img.stem}.txt")
    for c in cands:
        if c.is_file():
            return c
    return None


def parse_yolo(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    rows = []
    issues = []
    if not text:
        return {"empty": True, "rows": [], "issues": ["empty_negative_ok"]}
    for li, line in enumerate(text.splitlines(), 1):
        parts = line.split()
        if len(parts) != 5:
            issues.append({"line": li, "issue": "field_count", "raw": line[:80]})
            continue
        try:
            cid = int(float(parts[0]))
            xc, yc, w, h = [float(x) for x in parts[1:]]
        except ValueError:
            issues.append({"line": li, "issue": "parse_error", "raw": line[:80]})
            continue
        row_issues = []
        if cid not in VALID_CLASS_IDS:
            row_issues.append("invalid_class_id")
        if w <= 0 or h <= 0:
            row_issues.append("nonpositive_wh")
        if any(v < 0 or v > 1 for v in (xc, yc, w, h)):
            row_issues.append("coord_out_of_range")
        # box extent
        x1, y1 = xc - w / 2, yc - h / 2
        x2, y2 = xc + w / 2, yc + h / 2
        if x1 < -1e-6 or y1 < -1e-6 or x2 > 1 + 1e-6 or y2 > 1 + 1e-6:
            row_issues.append("box_outside_image")
        area = w * h
        if area < 1e-6:
            row_issues.append("zero_area")
        if area < 0.0002:
            row_issues.append("tiny_box")
        if area > 0.45:
            row_issues.append("huge_box")
        rows.append(
            {
                "cls": cid,
                "xywh": [xc, yc, w, h],
                "area": area,
                "issues": row_issues,
            }
        )
        for iss in row_issues:
            if iss in {"invalid_class_id", "nonpositive_wh", "coord_out_of_range", "box_outside_image", "zero_area"}:
                issues.append({"line": li, "issue": iss})
    # duplicate boxes
    seen = set()
    for r in rows:
        key = (r["cls"], tuple(round(x, 4) for x in r["xywh"]))
        if key in seen:
            issues.append({"line": None, "issue": "duplicate_box", "key": list(key)})
        seen.add(key)
    return {"empty": False, "rows": rows, "issues": issues}


def file_md5(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        while True:
            b = f.read(1 << 20)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def iou(a, b) -> float:
    axc, ayc, aw, ah = a
    bxc, byc, bw, bh = b
    ax1, ay1, ax2, ay2 = axc - aw / 2, ayc - ah / 2, axc + aw / 2, ayc + ah / 2
    bx1, by1, bx2, by2 = bxc - bw / 2, byc - bh / 2, bxc + bw / 2, byc + bh / 2
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    union = aw * ah + bw * bh - inter
    return inter / union if union > 0 else 0.0


def draw_samples(items: list[dict], out_dir: Path, limit: int, rng: random.Random) -> list[str]:
    if limit <= 0 or not items:
        out_dir.mkdir(parents=True, exist_ok=True)
        return []
    try:
        import cv2
    except Exception:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "OPENCV_UNAVAILABLE.txt").write_text("cv2 not available\n", encoding="utf-8")
        return []
    out_dir.mkdir(parents=True, exist_ok=True)
    pick = list(items)
    rng.shuffle(pick)
    written = []
    for item in pick[:limit]:
        img_path = Path(item["path"])
        lab_path = Path(item["label"]) if item.get("label") else None
        im = cv2.imread(str(img_path))
        if im is None:
            continue
        h, w = im.shape[:2]
        if lab_path and lab_path.is_file():
            parsed = parse_yolo(lab_path)
            for r in parsed["rows"]:
                xc, yc, bw, bh = r["xywh"]
                x1 = int((xc - bw / 2) * w)
                y1 = int((yc - bh / 2) * h)
                x2 = int((xc + bw / 2) * w)
                y2 = int((yc + bh / 2) * h)
                name = CLASS_NAMES.get(r["cls"], str(r["cls"]))
                color = (0, 255, 255) if not r["issues"] else (0, 0, 255)
                cv2.rectangle(im, (x1, y1), (x2, y2), color, 2)
                cv2.putText(
                    im,
                    name,
                    (x1, max(16, y1 - 4)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    color,
                    1,
                    cv2.LINE_AA,
                )
        else:
            cv2.putText(
                im,
                "NO LABEL FILE",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.0,
                (0, 0, 255),
                2,
                cv2.LINE_AA,
            )
        out = out_dir / f"{img_path.stem}.jpg"
        cv2.imwrite(str(out), im)
        written.append(str(out))
    return written


def main() -> int:
    args = parse_args()
    cand_path = Path(args.candidates)
    out_root = Path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)
    qa_vis = Path(__file__).resolve().parent / "runs" / "annotation_qa"
    for sub in ("representative", "hard_cases", "negatives", "per_class", "questionable", "pending_unlabeled"):
        (qa_vis / sub).mkdir(parents=True, exist_ok=True)

    report: dict = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "candidates_file": str(cand_path),
        "taxonomy": CLASS_NAMES,
        "critical": [],
        "warnings": [],
        "status": "UNKNOWN",
    }

    if not cand_path.is_file():
        report["critical"].append(f"candidates file missing: {cand_path}")
        report["status"] = "FAIL"
        (out_root / "annotation_completion.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        print(json.dumps(report, indent=2))
        return 2

    manifest = json.loads(cand_path.read_text(encoding="utf-8"))
    candidates = manifest.get("candidates") or []
    extra = []
    if args.label_roots:
        extra = [Path(x.strip()) for x in args.label_roots.split(",") if x.strip()]
    extra += [
        Path(__file__).resolve().parent / "annotation" / "prelabels",
        Path(__file__).resolve().parent / "annotation" / "labels",
    ]

    rng = random.Random(args.seed)
    per_image = []
    class_boxes: Counter[int] = Counter()
    class_images: dict[int, set[str]] = defaultdict(set)
    areas: dict[int, list[float]] = defaultdict(list)
    objects_per_image: list[int] = []
    critical_ann = 0
    empty_neg = 0
    missing = 0
    labeled = 0
    overlap_conflicts = 0

    for c in candidates:
        img = Path(c["path"])
        entry = {
            "path": str(img),
            "session_key": c.get("session_key") or session_key(img.stem),
            "priority": c.get("priority"),
            "exists": img.is_file(),
            "label": None,
            "empty": None,
            "n_boxes": 0,
            "issues": [],
        }
        if not img.is_file():
            entry["issues"].append("image_missing")
            report["critical"].append(f"missing image: {img}")
            per_image.append(entry)
            continue
        lab = find_label(img, extra)
        if lab is None:
            missing += 1
            entry["issues"].append("annotation_missing")
            per_image.append(entry)
            continue
        labeled += 1
        entry["label"] = str(lab)
        parsed = parse_yolo(lab)
        entry["empty"] = parsed["empty"]
        if parsed["empty"]:
            empty_neg += 1
            objects_per_image.append(0)
            per_image.append(entry)
            continue
        # severe overlap different classes
        rows = parsed["rows"]
        for i in range(len(rows)):
            for j in range(i + 1, len(rows)):
                if rows[i]["cls"] == rows[j]["cls"]:
                    continue
                if iou(rows[i]["xywh"], rows[j]["xywh"]) > 0.7:
                    overlap_conflicts += 1
                    parsed["issues"].append(
                        {"issue": "severe_overlap_conflict", "a": rows[i]["cls"], "b": rows[j]["cls"]}
                    )
        hard_issues = [
            x
            for x in parsed["issues"]
            if (isinstance(x, dict) and x.get("issue") not in {"empty_negative_ok", "tiny_box", "huge_box"})
            or (isinstance(x, str) and x not in {"empty_negative_ok"})
        ]
        if hard_issues:
            critical_ann += 1
        entry["issues"] = parsed["issues"]
        entry["n_boxes"] = len(rows)
        objects_per_image.append(len(rows))
        for r in rows:
            class_boxes[r["cls"]] += 1
            class_images[r["cls"]].add(img.stem)
            areas[r["cls"]].append(r["area"])
        per_image.append(entry)

    # class stats
    class_stats = {}
    for cid in sorted(VALID_CLASS_IDS):
        ar = sorted(areas.get(cid, []))
        class_stats[CLASS_NAMES[cid]] = {
            "class_id": cid,
            "object_count": class_boxes.get(cid, 0),
            "image_count": len(class_images.get(cid, set())),
            "area_min": ar[0] if ar else None,
            "area_median": ar[len(ar) // 2] if ar else None,
            "area_max": ar[-1] if ar else None,
            "tiny_pct": (
                round(100.0 * sum(1 for a in ar if a < 0.0002) / len(ar), 2) if ar else None
            ),
        }

    completion = {
        "total_candidates": len(candidates),
        "images_existing": sum(1 for e in per_image if e["exists"]),
        "manually_annotated_files": labeled,
        "missing_annotations": missing,
        "empty_negative_labels": empty_neg,
        "nonempty_labeled": labeled - empty_neg,
        "annotation_critical_files": critical_ann,
        "overlap_conflicts": overlap_conflicts,
        "objects_per_image": {
            "min": min(objects_per_image) if objects_per_image else None,
            "median": (
                sorted(objects_per_image)[len(objects_per_image) // 2]
                if objects_per_image
                else None
            ),
            "max": max(objects_per_image) if objects_per_image else None,
        },
        "class_stats": class_stats,
    }
    report["completion"] = completion

    if missing == len(candidates) and len(candidates) > 0:
        report["critical"].append(
            f"ANNOTATION INCOMPLETE: 0/{len(candidates)} candidate images have YOLO label files"
        )
    if critical_ann:
        report["critical"].append(f"{critical_ann} annotation files have critical geometry/class issues")

    # duplicates among candidate images
    hashes: dict[str, list[str]] = defaultdict(list)
    for e in per_image:
        if not e["exists"]:
            continue
        p = Path(e["path"])
        if args.hash_max and sum(len(v) for v in hashes.values()) >= args.hash_max:
            break
        try:
            hashes[file_md5(p)].append(e["path"])
        except Exception:
            continue
    dup_groups = [v for v in hashes.values() if len(v) > 1]
    # near-duplicate via session multiplicity in candidates
    sess = Counter(e["session_key"] for e in per_image)
    near = [k for k, n in sess.items() if n > 1]
    dup_report = {
        "exact_duplicate_groups": len(dup_groups),
        "exact_duplicate_extra_files": sum(len(g) - 1 for g in dup_groups),
        "sample_exact_groups": dup_groups[:10],
        "candidate_sessions": len(sess),
        "sessions_with_multiple_candidate_rows": len(near),
        "note": "Candidates were generated as one image per session; multiplicity>1 would be unexpected",
    }
    report["duplicates"] = dup_report

    # visual QA
    labeled_items = [e for e in per_image if e.get("label") and e.get("n_boxes", 0) > 0]
    negative_items = [e for e in per_image if e.get("label") and e.get("empty")]
    pending = [e for e in per_image if "annotation_missing" in e.get("issues", [])]
    visual = {
        "representative": draw_samples(labeled_items, qa_vis / "representative", args.visual_per_class, rng),
        "negatives": draw_samples(negative_items, qa_vis / "negatives", min(12, args.visual_per_class), rng),
        "pending_unlabeled": draw_samples(pending, qa_vis / "pending_unlabeled", 12, rng),
        "hard_cases": [],
        "questionable": [],
        "per_class": {},
    }
    # hard: tiny/huge if any
    hard = [
        e
        for e in labeled_items
        if any(
            (isinstance(i, dict) and i.get("issue") in {"tiny_box", "huge_box", "severe_overlap_conflict"})
            for i in e.get("issues", [])
        )
    ]
    visual["hard_cases"] = draw_samples(hard, qa_vis / "hard_cases", args.visual_per_class, rng)
    questionable = [e for e in labeled_items if e.get("issues")]
    visual["questionable"] = draw_samples(
        questionable, qa_vis / "questionable", args.visual_per_class, rng
    )
    for cid, name in CLASS_NAMES.items():
        cls_items = []
        for e in labeled_items:
            if not e.get("label"):
                continue
            parsed = parse_yolo(Path(e["label"]))
            if any(r["cls"] == cid for r in parsed["rows"]):
                cls_items.append(e)
        visual["per_class"][name] = draw_samples(
            cls_items, qa_vis / "per_class" / name, args.visual_per_class, rng
        )
    report["visual_qa_dir"] = str(qa_vis)
    report["visual_qa"] = {k: (len(v) if isinstance(v, list) else {a: len(b) for a, b in v.items()}) for k, v in visual.items()}

    if report["critical"]:
        report["status"] = "FAIL"
        code = 2
    else:
        report["status"] = "PASS"
        code = 0

    if args.fail_on_incomplete and missing:
        report["status"] = "FAIL"
        code = 2

    (out_root / "annotation_completion.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    (out_root / "annotation_per_image.json").write_text(
        json.dumps(per_image[:2000], indent=2), encoding="utf-8"
    )
    (out_root / "class_balance.json").write_text(
        json.dumps(class_stats, indent=2), encoding="utf-8"
    )
    (out_root / "duplicate_report.json").write_text(
        json.dumps(dup_report, indent=2), encoding="utf-8"
    )
    print(json.dumps({k: report[k] for k in report if k != "visual_qa"}, indent=2)[:8000])
    print(f"STATUS={report['status']} out={out_root}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
