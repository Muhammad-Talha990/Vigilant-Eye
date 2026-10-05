"""
VigilantEye AI-2 — Dataset forensics (NO TRAINING).

Inspects a placed dataset root recursively and writes JSON + optional visual QA.

Default source (authoritative placed data on this machine):
  <FYP or NEW>/ai/dataset/ufm/dataset

Note: literal path ai/dataset.ufm/dataset does not exist; use ai/dataset/ufm/dataset.

Usage (backend venv, project root):
  python ai/dataset_forensics.py --root "C:/Users/KING/Desktop/FYP/Vigilant Eye/ai/dataset/ufm/dataset"
  python ai/dataset_forensics.py --root ai/dataset/ufm/dataset --also-prepared ai/dataset/ufm
  python ai/dataset_forensics.py --fail-on-critical
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
VID_EXTS = {".mov", ".mp4", ".avi", ".mkv", ".wmv"}
ANN_EXTS = {".txt", ".xml", ".json", ".jsonl", ".csv"}
META_NAMES = {
    "data.yaml",
    "data.yml",
    "dataset.yaml",
    "readme.md",
    "readme.txt",
    "readme.dataset.txt",
    "readme.roboflow.txt",
    "classes.txt",
    "notes.json",
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="UFM dataset forensics (no training)")
    p.add_argument(
        "--root",
        type=str,
        required=True,
        help="Dataset root to inspect recursively",
    )
    p.add_argument(
        "--also-prepared",
        type=str,
        default="",
        help="Optional prepared YOLO root (images/ labels/ data.yaml)",
    )
    p.add_argument(
        "--out",
        type=str,
        default="",
        help="JSON report path (default: ai/runs/forensics/forensics_report.json)",
    )
    p.add_argument(
        "--visual-qa",
        type=int,
        default=12,
        help="Number of labeled samples to draw for visual QA (0=skip)",
    )
    p.add_argument(
        "--hash-sample",
        type=int,
        default=4000,
        help="Max images to content-hash for exact duplicates (0=skip)",
    )
    p.add_argument(
        "--video-probe-limit",
        type=int,
        default=0,
        help="Max videos to probe with OpenCV (0=all)",
    )
    p.add_argument(
        "--fail-on-critical",
        action="store_true",
        help="Exit 2 if critical dataset problems are found",
    )
    return p.parse_args()


def _rel(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except Exception:
        return str(path)


def file_md5(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def parse_yolo_label(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    rows = []
    bad = []
    if not text:
        return {"empty": True, "rows": [], "bad": [], "class_ids": []}
    for li, line in enumerate(text.splitlines(), 1):
        parts = line.split()
        if len(parts) != 5:
            bad.append({"line": li, "reason": "field_count", "raw": line[:80]})
            continue
        try:
            cid = int(float(parts[0]))
            vals = [float(x) for x in parts[1:]]
        except ValueError:
            bad.append({"line": li, "reason": "parse", "raw": line[:80]})
            continue
        xc, yc, w, h = vals
        issues = []
        if w <= 0 or h <= 0:
            issues.append("nonpositive_wh")
        if any(v < 0 or v > 1 for v in vals):
            issues.append("coord_out_of_range")
        if cid < 0:
            issues.append("negative_class")
        rows.append({"cls": cid, "xywh": vals, "issues": issues})
        if issues:
            bad.append({"line": li, "reason": ",".join(issues), "raw": line[:80]})
    return {
        "empty": False,
        "rows": rows,
        "bad": bad,
        "class_ids": [r["cls"] for r in rows],
    }


def probe_image(path: Path) -> dict:
    out = {"ok": False, "w": None, "h": None, "format": None, "error": None}
    try:
        from PIL import Image

        with Image.open(path) as im:
            im.verify()
        with Image.open(path) as im:
            out["w"], out["h"] = im.size
            out["format"] = im.format
            out["ok"] = True
    except Exception as exc:  # noqa: BLE001
        out["error"] = f"{type(exc).__name__}: {exc}"
    return out


def probe_video(path: Path) -> dict:
    info = {
        "name": path.name,
        "bytes": path.stat().st_size,
        "ok": False,
        "width": None,
        "height": None,
        "fps": None,
        "frame_count": None,
        "duration_sec": None,
        "error": None,
    }
    try:
        import cv2

        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            info["error"] = "open_failed"
            return info
        info["width"] = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        info["height"] = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0)
        n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        info["fps"] = round(fps, 3) if fps else None
        info["frame_count"] = n if n > 0 else None
        if fps > 0 and n > 0:
            info["duration_sec"] = round(n / fps, 2)
        # Read one frame to confirm decode
        ok, _ = cap.read()
        info["ok"] = bool(ok)
        if not ok:
            info["error"] = "decode_first_frame_failed"
        cap.release()
    except Exception as exc:  # noqa: BLE001
        info["error"] = f"{type(exc).__name__}: {exc}"
    return info


def infer_source_key(path: Path) -> str:
    """Heuristic source/session key for leakage-aware splits."""
    name = path.stem
    # Roboflow: 1001595_jpg.rf.hash
    m = re.match(r"^(\d+)_jpg\.rf\.", name, re.I)
    if m:
        return f"rf_id:{m.group(1)}"
    # Video frame: v_c1_s1_v1_f00030
    m = re.match(r"^(v_[a-z0-9_]+)_f\d+$", name, re.I)
    if m:
        return f"video:{m.group(1)}"
    # Prefix before .rf
    if ".rf." in name:
        return f"rf_stem:{name.split('.rf.')[0]}"
    # Leading numeric id
    m = re.match(r"^(\d+)", name)
    if m:
        return f"num:{m.group(1)}"
    return f"file:{name}"


def scan_tree(root: Path) -> dict:
    dirs: list[str] = []
    ext_counts: Counter[str] = Counter()
    images: list[Path] = []
    videos: list[Path] = []
    anns: list[Path] = []
    yamls: list[Path] = []
    readmes: list[Path] = []
    caches: list[Path] = []
    weights: list[Path] = []
    other_meta: list[Path] = []

    for p in root.rglob("*"):
        if p.is_dir():
            dirs.append(_rel(p, root))
            continue
        if not p.is_file():
            continue
        ext = p.suffix.lower()
        ext_counts[ext or "<none>"] += 1
        name_l = p.name.lower()
        if ext in IMG_EXTS:
            images.append(p)
        elif ext in VID_EXTS:
            videos.append(p)
        elif ext in ANN_EXTS:
            anns.append(p)
        if ext in {".yaml", ".yml"}:
            yamls.append(p)
        if name_l in META_NAMES or name_l.startswith("readme"):
            readmes.append(p)
        if ext == ".cache" or name_l.endswith(".cache"):
            caches.append(p)
        if ext == ".pt" or ext == ".onnx":
            weights.append(p)
        if name_l in {"notes.json", "classes.txt"}:
            other_meta.append(p)

    return {
        "dirs": sorted(dirs),
        "ext_counts": dict(sorted(ext_counts.items(), key=lambda x: (-x[1], x[0]))),
        "images": images,
        "videos": videos,
        "anns": anns,
        "yamls": yamls,
        "readmes": readmes,
        "caches": caches,
        "weights": weights,
        "other_meta": other_meta,
    }


def analyze_yolo_sidecar(images: list[Path]) -> dict:
    """Labels expected as same-stem .txt beside image OR in parallel labels/ tree."""
    labeled = 0
    unlabeled = 0
    empty_labels = 0
    missing_label_files = 0
    class_boxes: Counter[int] = Counter()
    images_with_class: dict[int, set[str]] = defaultdict(set)
    bad_files = 0
    bad_rows = 0
    label_paths_used: list[str] = []

    for img in images:
        # 1) sidecar
        cand = img.with_suffix(".txt")
        # 2) .../images/... -> .../labels/...
        alt = None
        parts = list(img.parts)
        if "images" in parts:
            i = parts.index("images")
            alt_parts = parts[:i] + ["labels"] + parts[i + 1 :]
            alt = Path(*alt_parts).with_suffix(".txt")
        # 3) Roboflow flat split: train/img.jpg with train/labels elsewhere uncommon;
        #    this CCTV export may have no labels at all.
        lab = None
        if cand.is_file():
            lab = cand
        elif alt is not None and alt.is_file():
            lab = alt
        if lab is None:
            unlabeled += 1
            missing_label_files += 1
            continue
        labeled += 1
        label_paths_used.append(str(lab))
        parsed = parse_yolo_label(lab)
        if parsed["empty"]:
            empty_labels += 1
            continue
        if parsed["bad"]:
            bad_files += 1
            bad_rows += len(parsed["bad"])
        for cid in parsed["class_ids"]:
            class_boxes[cid] += 1
            images_with_class[cid].add(img.name)

    total_boxes = sum(class_boxes.values())
    per_class = {}
    for cid, n in sorted(class_boxes.items()):
        per_class[str(cid)] = {
            "boxes": n,
            "images_containing": len(images_with_class[cid]),
            "pct_boxes": round(100.0 * n / total_boxes, 3) if total_boxes else 0.0,
            "pct_labeled_images": (
                round(100.0 * len(images_with_class[cid]) / labeled, 3)
                if labeled
                else 0.0
            ),
        }

    return {
        "images_total": len(images),
        "labeled_images": labeled,
        "unlabeled_images": unlabeled,
        "empty_label_files": empty_labels,
        "missing_label_files": missing_label_files,
        "bad_label_files": bad_files,
        "bad_label_rows": bad_rows,
        "total_boxes": total_boxes,
        "class_distribution": per_class,
        "label_files_found": len(set(label_paths_used)),
    }


def analyze_prepared_yolo(prepared: Path) -> dict:
    report: dict = {"path": str(prepared), "exists": prepared.is_dir()}
    if not prepared.is_dir():
        return report
    data_yaml = prepared / "data.yaml"
    names = {}
    if data_yaml.is_file():
        try:
            import yaml

            data = yaml.safe_load(data_yaml.read_text(encoding="utf-8")) or {}
            names = data.get("names") or {}
            report["data_yaml"] = data
        except Exception as exc:  # noqa: BLE001
            report["data_yaml_error"] = str(exc)
    report["class_names"] = names
    splits = {}
    for split in ("train", "val", "test"):
        img_dir = prepared / "images" / split
        lab_dir = prepared / "labels" / split
        imgs = (
            sorted(p for p in img_dir.iterdir() if p.suffix.lower() in IMG_EXTS)
            if img_dir.is_dir()
            else []
        )
        labs = (
            sorted(p for p in lab_dir.glob("*.txt")) if lab_dir.is_dir() else []
        )
        yolo = analyze_yolo_sidecar(imgs) if imgs else {
            "images_total": 0,
            "labeled_images": 0,
            "unlabeled_images": 0,
            "total_boxes": 0,
            "class_distribution": {},
        }
        # Prefer labels/ tree pairing
        class_boxes: Counter[int] = Counter()
        images_with_class: dict[int, set[str]] = defaultdict(set)
        empty = 0
        bad_rows = 0
        for lab in labs:
            parsed = parse_yolo_label(lab)
            if parsed["empty"]:
                empty += 1
                continue
            bad_rows += len(parsed["bad"])
            stem = lab.stem
            for cid in parsed["class_ids"]:
                class_boxes[cid] += 1
                images_with_class[cid].add(stem)
        total_boxes = sum(class_boxes.values())
        dist = {}
        for cid, n in sorted(class_boxes.items()):
            cname = (
                names.get(cid, names.get(str(cid), str(cid)))
                if isinstance(names, dict)
                else str(cid)
            )
            dist[str(cid)] = {
                "name": cname,
                "boxes": n,
                "images_containing": len(images_with_class[cid]),
                "pct_boxes": round(100.0 * n / total_boxes, 3) if total_boxes else 0.0,
            }
        # Source leakage heuristic
        sources = Counter(infer_source_key(p) for p in imgs)
        splits[split] = {
            "images": len(imgs),
            "label_files": len(labs),
            "empty_labels": empty,
            "bad_label_rows": bad_rows,
            "total_boxes": total_boxes,
            "class_distribution": dist,
            "unique_source_keys": len(sources),
            "top_sources": sources.most_common(10),
            "sidecar_analysis": yolo,
        }
    report["splits"] = splits
    return report


def draw_visual_qa(
    prepared: Path, out_dir: Path, limit: int, names: dict
) -> list[str]:
    if limit <= 0:
        return []
    try:
        import cv2
    except Exception:
        return []
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    candidates: list[tuple[Path, Path]] = []
    for split in ("train", "val", "test"):
        img_dir = prepared / "images" / split
        lab_dir = prepared / "labels" / split
        if not img_dir.is_dir() or not lab_dir.is_dir():
            continue
        for lab in lab_dir.glob("*.txt"):
            if lab.stat().st_size == 0:
                continue
            for ext in IMG_EXTS:
                img = img_dir / f"{lab.stem}{ext}"
                if img.is_file():
                    candidates.append((img, lab))
                    break
    # Prefer diversity of class presence
    random_pick = candidates[: max(limit * 3, limit)]
    for img_path, lab_path in random_pick:
        if len(written) >= limit:
            break
        parsed = parse_yolo_label(lab_path)
        if not parsed["rows"]:
            continue
        im = cv2.imread(str(img_path))
        if im is None:
            continue
        h, w = im.shape[:2]
        for row in parsed["rows"]:
            cid = row["cls"]
            xc, yc, bw, bh = row["xywh"]
            x1 = int((xc - bw / 2) * w)
            y1 = int((yc - bh / 2) * h)
            x2 = int((xc + bw / 2) * w)
            y2 = int((yc + bh / 2) * h)
            cname = (
                names.get(cid, names.get(str(cid), str(cid)))
                if isinstance(names, dict)
                else str(cid)
            )
            cv2.rectangle(im, (x1, y1), (x2, y2), (0, 255, 255), 2)
            cv2.putText(
                im,
                f"{cname}",
                (x1, max(16, y1 - 4)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 255),
                1,
                cv2.LINE_AA,
            )
        out = out_dir / f"qa_{img_path.stem}.jpg"
        cv2.imwrite(str(out), im)
        written.append(str(out))
    return written


def main() -> int:
    args = parse_args()
    root = Path(args.root)
    ai_root = Path(__file__).resolve().parent
    out = (
        Path(args.out)
        if args.out
        else ai_root / "runs" / "forensics" / "forensics_report.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)

    report: dict = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "requested_root": str(root),
        "root_exists": root.is_dir(),
        "note_path_typo": (
            "Literal ai/dataset.ufm/dataset was not found on disk; "
            "authoritative placed path is ai/dataset/ufm/dataset"
        ),
        "critical_problems": [],
        "warnings": [],
    }

    if not root.is_dir():
        report["critical_problems"].append(f"Root does not exist: {root}")
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 2 if args.fail_on_critical else 1

    tree = scan_tree(root)
    report["inventory"] = {
        "directory_count": len(tree["dirs"]),
        "directories_sample": tree["dirs"][:80],
        "extension_counts": tree["ext_counts"],
        "image_count": len(tree["images"]),
        "video_count": len(tree["videos"]),
        "annotation_file_count": len(tree["anns"]),
        "yaml_files": [_rel(p, root) for p in tree["yamls"]],
        "readme_meta_files": [_rel(p, root) for p in tree["readmes"]],
        "cache_files": [_rel(p, root) for p in tree["caches"]],
        "weight_files": [_rel(p, root) for p in tree["weights"]],
        "videos": [_rel(p, root) for p in sorted(tree["videos"])],
    }

    # Per top-level collection
    collections = {}
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        imgs = [p for p in child.rglob("*") if p.is_file() and p.suffix.lower() in IMG_EXTS]
        vids = [p for p in child.rglob("*") if p.is_file() and p.suffix.lower() in VID_EXTS]
        txts = [p for p in child.rglob("*.txt") if p.is_file()]
        # Exclude readmes from label-like txt
        label_like = [
            p
            for p in txts
            if p.name.lower() not in {
                "readme.md.txt",
                "readme.txt",
                "readme.dataset.txt",
                "readme.roboflow.txt",
                "classes.txt",
            }
            and "readme" not in p.name.lower()
        ]
        yolo_ann = analyze_yolo_sidecar(imgs)
        # Resolution sample
        res_counter: Counter[str] = Counter()
        corrupt = 0
        sampled = imgs[: min(len(imgs), 800)]
        for ip in sampled:
            meta = probe_image(ip)
            if not meta["ok"]:
                corrupt += 1
            elif meta["w"] and meta["h"]:
                res_counter[f"{meta['w']}x{meta['h']}"] += 1
        collections[child.name] = {
            "images": len(imgs),
            "videos": len(vids),
            "txt_files_total": len(txts),
            "label_like_txt_files": len(label_like),
            "yolo_pairing": yolo_ann,
            "resolution_sample_n": len(sampled),
            "corrupt_or_unreadable_in_sample": corrupt,
            "top_resolutions": res_counter.most_common(10),
            "has_train_val_test": {
                "train": (child / "train").is_dir(),
                "valid": (child / "valid").is_dir() or (child / "val").is_dir(),
                "test": (child / "test").is_dir(),
            },
        }
        if yolo_ann["labeled_images"] == 0 and len(imgs) > 0:
            report["critical_problems"].append(
                f"Collection '{child.name}': {len(imgs)} images but 0 paired YOLO labels"
            )
        if len(vids) and len(label_like) == 0:
            report["warnings"].append(
                f"Collection '{child.name}': {len(vids)} videos with no annotation files"
            )
    report["collections"] = collections

    # YAML class lists
    yaml_classes = {}
    for yp in tree["yamls"]:
        try:
            import yaml

            data = yaml.safe_load(yp.read_text(encoding="utf-8")) or {}
            yaml_classes[_rel(yp, root)] = {
                "names": data.get("names"),
                "nc": data.get("nc"),
                "train": data.get("train"),
                "val": data.get("val"),
                "test": data.get("test"),
            }
        except Exception as exc:  # noqa: BLE001
            yaml_classes[_rel(yp, root)] = {"error": str(exc)}
    report["yaml_configs"] = yaml_classes

    # Exact duplicate hashes (sample)
    if args.hash_sample > 0 and tree["images"]:
        sample = tree["images"][: args.hash_sample]
        hashes: dict[str, list[str]] = defaultdict(list)
        for ip in sample:
            try:
                hashes[file_md5(ip)].append(_rel(ip, root))
            except Exception:
                continue
        dup_groups = [v for v in hashes.values() if len(v) > 1]
        report["duplicate_analysis"] = {
            "hashed_images": len(sample),
            "unique_hashes": len(hashes),
            "exact_duplicate_groups": len(dup_groups),
            "exact_duplicate_extra_files": sum(len(g) - 1 for g in dup_groups),
            "sample_groups": dup_groups[:15],
        }
    else:
        report["duplicate_analysis"] = {"skipped": True}

    # Source-key collision across Roboflow-style names
    src_keys = Counter(infer_source_key(p) for p in tree["images"])
    report["source_key_analysis"] = {
        "unique_keys": len(src_keys),
        "images": len(tree["images"]),
        "keys_with_multiple_images": sum(1 for _, n in src_keys.items() if n > 1),
        "top_keys": src_keys.most_common(15),
        "split_strategy": (
            "Assign each source_key to exactly one of train/val/test. "
            "Never split frames sharing the same video:* or rf_id:* key across splits."
        ),
    }

    # Videos
    vids = sorted(tree["videos"])
    if args.video_probe_limit > 0:
        vids = vids[: args.video_probe_limit]
    video_reports = [probe_video(v) for v in vids]
    report["videos"] = {
        "count": len(tree["videos"]),
        "probed": len(video_reports),
        "items": video_reports,
        "total_duration_sec_probed": round(
            sum(v["duration_sec"] or 0 for v in video_reports), 2
        ),
        "approx_total_frames_probed": sum(v["frame_count"] or 0 for v in video_reports),
        "annotations_present_for_videos": False,
        "frame_sampling_recommendation": {
            "every_n_frames": 30,
            "max_frames_per_video": 8,
            "reason": (
                "Avoid near-duplicate consecutive frames; keep session identity "
                "in filename prefix for leakage-safe splits."
            ),
        },
    }

    # Prepared weak-label set
    if args.also_prepared:
        prepared = Path(args.also_prepared)
        prep = analyze_prepared_yolo(prepared)
        report["prepared_yolo_set"] = prep
        names = prep.get("class_names") or {}
        qa_dir = out.parent / "visual_qa"
        qa_files = draw_visual_qa(prepared, qa_dir, args.visual_qa, names)
        report["visual_qa_files"] = qa_files
        # Weak label verdict
        total_boxes = sum(
            s.get("total_boxes", 0) for s in (prep.get("splits") or {}).values()
        )
        report["weak_label_analysis"] = {
            "generator": "prepare_placed_dataset.py (COCO→UFM weak labels)",
            "mapping": {
                "cell phone": "mobile_phone",
                "book": "notes_paper",
                "laptop/keyboard/mouse": "electronic_gadget",
                "suitcase/handbag/backpack": "suspicious_object",
                "smart_watch": "NOT produced by COCO",
            },
            "total_boxes_in_prepared": total_boxes,
            "suitable_for_final_fyp_training": False,
            "reason": (
                "Weak labels are COCO detections remapped to UFM names — not "
                "human-verified exam annotations. Prior custom train/eval collapsed "
                "(mAP50≈0.00367). Retain only as experimental artifacts."
            ),
            "recommendation": "DISCARD from final training set; keep under experimental/",
        }

    # Global annotation format summary
    ann_by_ext = Counter(p.suffix.lower() for p in tree["anns"])
    report["annotation_formats"] = {
        "files_by_extension": dict(ann_by_ext),
        "coco_json_detected": any(p.name.lower() == "annotations.json" or "coco" in p.name.lower() for p in tree["anns"] if p.suffix.lower() == ".json"),
        "yolo_txt_detected": ann_by_ext.get(".txt", 0) > 0,
        "pascal_voc_xml_detected": ann_by_ext.get(".xml", 0) > 0,
    }

    # Suitability gate summary flags
    total_imgs = report["inventory"]["image_count"]
    total_labeled = sum(
        c["yolo_pairing"]["labeled_images"] for c in collections.values()
    )
    if total_imgs > 0 and total_labeled == 0:
        report["critical_problems"].append(
            "No paired YOLO bounding-box labels found for any placed images"
        )
    if report["inventory"]["video_count"] and not total_labeled:
        report["warnings"].append(
            "Videos exist but provide no object annotations; useful only after frame sampling + manual labeling or as temporal behavior data"
        )

    report["gate"] = {
        "status_recommendation": (
            "C — DATASET NOT READY"
            if report["critical_problems"]
            else "B — DATASET PARTIALLY READY — ANNOTATION REQUIRED"
        ),
        "labeled_image_count_in_placed_root": total_labeled,
        "image_count": total_imgs,
        "video_count": report["inventory"]["video_count"],
    }

    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2)[:12000])
    print(f"\n... full report: {out}")

    if args.fail_on_critical and report["critical_problems"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
