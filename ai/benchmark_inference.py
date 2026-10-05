"""
Measure YOLO inference latency / throughput on representative images.

Reports MODEL INFERENCE latency only (not end-to-end monitoring latency).

Usage:
  python ai/benchmark_inference.py
  python ai/benchmark_inference.py --weights ai/weights/yolov8n.pt --imgsz 640
"""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Benchmark VigilantEye YOLO inference")
    p.add_argument(
        "--weights",
        type=str,
        default=str(ROOT / "weights" / "yolov8n.pt"),
    )
    p.add_argument("--imgsz", type=int, default=640)
    p.add_argument("--warmup", type=int, default=3)
    p.add_argument("--runs", type=int, default=20)
    p.add_argument("--device", type=str, default="cpu")
    p.add_argument(
        "--source",
        type=str,
        default=str(ROOT / "samples" / "phone_under_desk.jpg"),
        help="Image or video; first readable frame is used",
    )
    p.add_argument(
        "--outdir",
        type=str,
        default=str(ROOT / "runs" / "bench"),
    )
    return p.parse_args()


def _load_bgr(path: Path) -> np.ndarray:
    if path.suffix.lower() in {".mp4", ".avi", ".mkv", ".mov"}:
        cap = cv2.VideoCapture(str(path))
        ok, frame = cap.read()
        cap.release()
        if not ok or frame is None:
            raise RuntimeError(f"Could not read frame from {path}")
        return frame
    img = cv2.imread(str(path))
    if img is None:
        raise RuntimeError(f"Could not read image {path}")
    return img


def main() -> int:
    args = parse_args()
    weights = Path(args.weights)
    source = Path(args.source)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    report: dict = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "kind": "MODEL_INFERENCE_LATENCY",
        "weights": str(weights),
        "weights_exist": weights.is_file(),
        "source": str(source),
        "imgsz": args.imgsz,
        "device_requested": args.device,
        "warmup": args.warmup,
        "runs": args.runs,
        "python": sys.version,
        "platform": platform.platform(),
        "status": "NOT_RUN",
        "blocker": None,
    }

    if not weights.is_file():
        report["status"] = "BLOCKED"
        report["blocker"] = f"Weights not found: {weights}"
        (outdir / "bench_report.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        print(json.dumps(report, indent=2))
        return 2

    try:
        import torch
        from ultralytics import YOLO

        report["torch"] = torch.__version__
        report["cuda_available"] = bool(torch.cuda.is_available())
        frame = _load_bgr(source)
        report["frame_shape"] = list(frame.shape)
        model = YOLO(str(weights))
        for _ in range(args.warmup):
            model.predict(frame, imgsz=args.imgsz, verbose=False, device=args.device)

        times_ms: list[float] = []
        for _ in range(args.runs):
            t0 = time.perf_counter()
            model.predict(frame, imgsz=args.imgsz, verbose=False, device=args.device)
            times_ms.append((time.perf_counter() - t0) * 1000.0)

        report["status"] = "MEASURED"
        report["latency_ms"] = {
            "mean": round(statistics.mean(times_ms), 2),
            "median": round(statistics.median(times_ms), 2),
            "p95": round(sorted(times_ms)[max(0, int(0.95 * len(times_ms)) - 1)], 2),
            "min": round(min(times_ms), 2),
            "max": round(max(times_ms), 2),
        }
        mean = report["latency_ms"]["mean"]
        report["throughput_fps_theoretical"] = (
            round(1000.0 / mean, 2) if mean > 0 else None
        )
        report["note"] = (
            "Theoretical FPS = 1000/mean_ms for a single stream with no "
            "detect_every skip. Live pipeline also samples frames (LIVE_DETECT_EVERY)."
        )
    except Exception as exc:  # noqa: BLE001
        report["status"] = "BLOCKED"
        report["blocker"] = f"{type(exc).__name__}: {exc}"

    out = outdir / "bench_report.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "MEASURED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
