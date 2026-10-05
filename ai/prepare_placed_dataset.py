"""
Prepare the user-placed external datasets under ai/dataset/ufm/dataset/
into VigilantEye YOLO layout (images/ + labels/) and weak-label with COCO YOLO.

Sources supported:
  1) CCTV-Exam -Monitor -Dataset  (Roboflow-style split folders; images only)
  2) Dataset_cheating             (unlabeled MOV/AVI — extract frames)

The placed CCTV export currently has NO .txt labels. This script creates
COCO→UFM weak boxes so train_yolo.py can run. Hand-fix labels later for
production quality.

Usage (project root, backend venv):
  python ai/prepare_placed_dataset.py
  python ai/prepare_placed_dataset.py --max-train 800 --max-val 160
  python ai/train_yolo.py --epochs 40 --batch 4 --name ufm_custom
"""

from __future__ import annotations

import argparse
import random
import shutil
from pathlib import Path

from ultralytics import YOLO

from ufm_classes import AI_ROOT, default_coco_weights

# Placed-dataset bootstrap vocabulary (must match data.yaml written below).
# NOTE: COCO cannot produce smart_watch / normal_watch — those stay untrained
# until hand-labeled or a watch-specific export is merged.
PLACED_CLASS_NAMES = [
    "mobile_phone",  # 0
    "smart_watch",  # 1 — not produced by COCO weak labels
    "notes_paper",  # 2
    "electronic_gadget",  # 3
    "suspicious_object",  # 4
]

COCO_TO_UFM_INDEX = {
    "cell phone": 0,
    "book": 2,
    "laptop": 3,
    "keyboard": 3,
    "mouse": 3,
    # remote intentionally omitted — high FP on watch-like shapes
    "suitcase": 4,
    "handbag": 4,
    "backpack": 4,
}

IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
VID_EXTS = {".mov", ".avi", ".mp4", ".mkv"}


def parse_args() -> argparse.Namespace:
    root = AI_ROOT / "dataset" / "ufm"
    parser = argparse.ArgumentParser(
        description="Import placed datasets and weak-label for UFM YOLO training"
    )
    parser.add_argument(
        "--source-root",
        type=str,
        default=str(root / "dataset"),
        help="Folder containing CCTV / Dataset_cheating",
    )
    parser.add_argument(
        "--dest",
        type=str,
        default=str(root),
        help="YOLO dataset root (images/ + labels/)",
    )
    parser.add_argument(
        "--weights",
        type=str,
        default=str(default_coco_weights()),
        help="COCO YOLO weights for weak labeling",
    )
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument(
        "--max-train",
        type=int,
        default=800,
        help="Cap training images (CPU-friendly). Use 0 for all.",
    )
    parser.add_argument(
        "--max-val",
        type=int,
        default=160,
        help="Cap validation images. Use 0 for all.",
    )
    parser.add_argument(
        "--include-cheating-videos",
        action="store_true",
        default=True,
        help="Extract frames from Dataset_cheating videos (default on)",
    )
    parser.add_argument(
        "--no-cheating-videos",
        action="store_true",
        help="Skip Dataset_cheating video frame extraction",
    )
    parser.add_argument(
        "--video-every",
        type=int,
        default=30,
        help="Keep every Nth frame from cheating videos",
    )
    parser.add_argument(
        "--max-frames-per-video",
        type=int,
        default=8,
        help="Max frames kept per cheating video",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear existing images/labels train|val before import",
    )
    parser.add_argument(
        "--device",
        type=str,
        default="cpu",
        help="Inference device for auto-label",
    )
    return parser.parse_args()


def find_cctv_dir(source_root: Path) -> Path | None:
    for p in source_root.iterdir():
        if not p.is_dir():
            continue
        name = p.name.lower()
        if "cctv" in name or "monitor" in name:
            return p
    # fallback: any dir with train/ + jpg
    for p in source_root.iterdir():
        if p.is_dir() and (p / "train").is_dir():
            return p
    return None


def find_cheating_dir(source_root: Path) -> Path | None:
    for p in source_root.iterdir():
        if p.is_dir() and "cheating" in p.name.lower():
            return p
    return None


def list_images(folder: Path) -> list[Path]:
    if not folder.is_dir():
        return []
    return sorted(
        f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in IMG_EXTS
    )


def clear_split(dest: Path) -> None:
    for split in ("train", "val"):
        for kind in ("images", "labels"):
            d = dest / kind / split
            if d.is_dir():
                shutil.rmtree(d)
            d.mkdir(parents=True, exist_ok=True)


def extract_video_frames(
    video_path: Path,
    out_dir: Path,
    every: int,
    max_frames: int,
) -> list[Path]:
    import cv2

    out_dir.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"SKIP video: {video_path.name}")
        return []
    saved: list[Path] = []
    idx = 0
    kept = 0
    while kept < max_frames:
        ok, frame = cap.read()
        if not ok:
            break
        if idx % max(1, every) == 0:
            name = f"{video_path.stem}_f{idx:05d}.jpg"
            path = out_dir / name
            cv2.imwrite(str(path), frame)
            saved.append(path)
            kept += 1
        idx += 1
    cap.release()
    return saved


def yolo_line(cls_id: int, xywhn) -> str:
    x, y, w, h = [float(v) for v in xywhn]
    return f"{cls_id} {x:.6f} {y:.6f} {w:.6f} {h:.6f}"


def auto_label_batch(
    model: YOLO,
    image_paths: list[Path],
    conf: float,
    device: str,
) -> dict[Path, list[str]]:
    """Predict on paths; return mapping path -> YOLO label lines."""
    out: dict[Path, list[str]] = {p: [] for p in image_paths}
    if not image_paths:
        return out
    # Process in chunks to limit memory
    chunk = 16
    for i in range(0, len(image_paths), chunk):
        batch = image_paths[i : i + chunk]
        results = model.predict(
            [str(p) for p in batch],
            conf=conf,
            device=device,
            verbose=False,
        )
        for path, result in zip(batch, results):
            lines: list[str] = []
            names = result.names
            if result.boxes is not None and len(result.boxes) > 0:
                for box in result.boxes:
                    cls_id = int(box.cls[0].item())
                    coco_name = names.get(cls_id, "")
                    ufm_id = COCO_TO_UFM_INDEX.get(coco_name)
                    if ufm_id is None:
                        continue
                    lines.append(yolo_line(ufm_id, box.xywhn[0].tolist()))
            out[path] = lines
        print(f"  labeled {min(i + chunk, len(image_paths))}/{len(image_paths)}")
    return out


def copy_and_write(
    items: list[tuple[Path, list[str]]],
    img_dir: Path,
    lbl_dir: Path,
) -> tuple[int, int]:
    img_dir.mkdir(parents=True, exist_ok=True)
    lbl_dir.mkdir(parents=True, exist_ok=True)
    labeled = 0
    empty = 0
    for src, lines in items:
        # Avoid collisions across sources
        dest_name = src.name
        dest_img = img_dir / dest_name
        if dest_img.exists():
            dest_name = f"{src.stem}_{abs(hash(str(src))) % 10_000_000}{src.suffix}"
            dest_img = img_dir / dest_name
        shutil.copy2(src, dest_img)
        (lbl_dir / f"{Path(dest_name).stem}.txt").write_text(
            ("\n".join(lines) + "\n") if lines else "",
            encoding="utf-8",
        )
        if lines:
            labeled += 1
        else:
            empty += 1
    return labeled, empty


def sample_list(files: list[Path], limit: int, seed: int) -> list[Path]:
    if limit <= 0 or len(files) <= limit:
        return files
    rng = random.Random(seed)
    picked = files[:]
    rng.shuffle(picked)
    return picked[:limit]


def main() -> None:
    args = parse_args()
    source_root = Path(args.source_root)
    dest = Path(args.dest)
    include_videos = args.include_cheating_videos and not args.no_cheating_videos

    if not source_root.is_dir():
        raise SystemExit(f"Source root not found: {source_root}")

    cctv = find_cctv_dir(source_root)
    cheat = find_cheating_dir(source_root)
    if cctv is None and cheat is None:
        raise SystemExit(f"No CCTV or Dataset_cheating folder under {source_root}")

    if args.clear:
        clear_split(dest)
        print("Cleared existing train/val images and labels.")

    train_imgs: list[Path] = []
    val_imgs: list[Path] = []

    if cctv is not None:
        train_imgs.extend(list_images(cctv / "train"))
        # Roboflow uses "valid"; accept "val" too
        val_imgs.extend(list_images(cctv / "valid") or list_images(cctv / "val"))
        print(f"CCTV source: {cctv}")
        print(f"  train images available: {len(train_imgs)}")
        print(f"  val images available:   {len(val_imgs)}")
    else:
        print("No CCTV folder found.")

    frame_dir = AI_ROOT / "dataset" / "_extracted_cheating_frames"
    if include_videos and cheat is not None:
        videos = sorted(
            p
            for p in cheat.iterdir()
            if p.is_file() and p.suffix.lower() in VID_EXTS
        )
        print(f"Cheating videos: {len(videos)} under {cheat.name}")
        # Session-aware: assign each VIDEO wholly to train or val (no frame leakage).
        rng = random.Random(args.seed)
        vids = videos[:]
        rng.shuffle(vids)
        n_val_vids = max(1, int(len(vids) * 0.2)) if len(vids) >= 5 else 0
        val_vids = set(vids[:n_val_vids])
        for vp in vids:
            got = extract_video_frames(
                vp, frame_dir / vp.stem, args.video_every, args.max_frames_per_video
            )
            print(f"  {vp.name}: {len(got)} frames → {'val' if vp in val_vids else 'train'}")
            if vp in val_vids:
                val_imgs.extend(got)
            else:
                train_imgs.extend(got)
    elif cheat is None:
        print("No Dataset_cheating folder found.")

    # Cap sizes but keep CCTV source split (train folder vs valid folder).
    train_imgs = sample_list(train_imgs, args.max_train, args.seed)
    val_imgs = sample_list(val_imgs, args.max_val, args.seed + 1)

    if not train_imgs:
        raise SystemExit("No training images selected.")

    # Persist class map used for this dataset version
    yaml_text = (
        "# VigilantEye placed-dataset bootstrap (YOLO format)\n"
        "# Labels are COCO weak-labels unless hand-corrected.\n"
        "path: .\n"
        "train: images/train\n"
        "val: images/val\n"
        "names:\n"
        + "".join(f"  {i}: {n}\n" for i, n in enumerate(PLACED_CLASS_NAMES))
    )
    (dest / "data.yaml").write_text(yaml_text, encoding="utf-8")
    (dest / "DATASET_VERSION.txt").write_text(
        "version=placed_weak_coco_v1\n"
        "label_source=coco_yolov8n_weak\n"
        "note=smart_watch has no COCO weak labels; hand annotation required\n"
        "split=cctv_train_valid_folders + video_session_aware\n",
        encoding="utf-8",
    )

    print("=" * 60)
    print("Weak-labeling with COCO YOLO → UFM classes")
    print(f"classes : {PLACED_CLASS_NAMES}")
    print(f"train   : {len(train_imgs)}")
    print(f"val     : {len(val_imgs)}")
    print(f"weights : {args.weights}")
    print("LIMITATION: labels are COCO weak boxes — not hand-verified exam labels.")
    print("=" * 60)

    model = YOLO(args.weights)
    train_labels = auto_label_batch(model, train_imgs, args.conf, args.device)
    val_labels = auto_label_batch(model, val_imgs, args.conf, args.device)

    t_lab, t_empty = copy_and_write(
        [(p, train_labels[p]) for p in train_imgs],
        dest / "images" / "train",
        dest / "labels" / "train",
    )
    v_lab, v_empty = copy_and_write(
        [(p, val_labels[p]) for p in val_imgs],
        dest / "images" / "val",
        dest / "labels" / "val",
    )

    print()
    print(f"Train: labeled={t_lab}, empty={t_empty}")
    print(f"Val:   labeled={v_lab}, empty={v_empty}")
    if t_lab == 0:
        raise SystemExit(
            "No non-empty training labels produced. "
            "Lower --conf or add hand annotations."
        )
    print()
    print("Next:")
    print("  python ai/train_yolo.py --epochs 15 --batch 4 --imgsz 640 --name ufm_custom --device cpu")
    print("  python ai/evaluate_model.py --weights ai/runs/train/ufm_custom/weights/best.pt")
    print("  python ai/test_detector.py --source ai/samples/phone_under_desk.jpg")


if __name__ == "__main__":
    main()
