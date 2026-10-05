"""
Evaluate a VigilantEye YOLO checkpoint on the prepared val split.

Writes JSON metrics under ai/runs/eval/ — never invents numbers.

Usage:
  python ai/evaluate_model.py
  python ai/evaluate_model.py --weights ai/runs/train/ufm_custom/weights/best.pt
  python ai/evaluate_model.py --weights ai/weights/yolov8n.pt --coco-baseline
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Evaluate VigilantEye YOLO weights")
    p.add_argument(
        "--weights",
        type=str,
        default=str(ROOT / "runs" / "train" / "ufm_custom" / "weights" / "best.pt"),
    )
    p.add_argument(
        "--data",
        type=str,
        default=str(ROOT / "dataset" / "ufm" / "data.yaml"),
    )
    p.add_argument("--imgsz", type=int, default=416)
    p.add_argument("--batch", type=int, default=1)
    p.add_argument("--device", type=str, default="cpu")
    p.add_argument(
        "--coco-baseline",
        action="store_true",
        help="Skip custom-dataset val (COCO class mismatch); only record identity",
    )
    p.add_argument(
        "--outdir",
        type=str,
        default=str(ROOT / "runs" / "eval"),
    )
    return p.parse_args()


def _write_resolved(data_yaml: Path) -> Path:
    import yaml

    data = yaml.safe_load(data_yaml.read_text(encoding="utf-8")) or {}
    data["path"] = str(data_yaml.parent.resolve()).replace("\\", "/")
    data.setdefault("train", "images/train")
    data.setdefault("val", "images/val")
    out = data_yaml.parent / "_data_resolved.yaml"
    out.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return out


def main() -> int:
    args = parse_args()
    weights = Path(args.weights)
    data_yaml = Path(args.data)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    report: dict = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "weights": str(weights.resolve()) if weights.is_file() else str(weights),
        "weights_exist": weights.is_file(),
        "data_yaml": str(data_yaml.resolve()) if data_yaml.is_file() else str(data_yaml),
        "imgsz": args.imgsz,
        "batch": args.batch,
        "device": args.device,
        "python": sys.version,
        "platform": platform.platform(),
        "status": "NOT_RUN",
        "metrics": None,
        "blocker": None,
    }

    if not weights.is_file():
        report["status"] = "BLOCKED"
        report["blocker"] = f"Weights not found: {weights}"
        out = outdir / "eval_report.json"
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 2

    if args.coco_baseline:
        report["status"] = "SKIPPED_COCO_BASELINE"
        report["blocker"] = (
            "COCO class IDs/names do not match custom UFM data.yaml; "
            "mAP on UFM val is not comparable. Use custom best.pt for dataset eval."
        )
        out = outdir / "eval_report_coco.json"
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 0

    if not data_yaml.is_file():
        report["status"] = "BLOCKED"
        report["blocker"] = f"Dataset yaml not found: {data_yaml}"
        out = outdir / "eval_report.json"
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 2

    try:
        import io
        import yaml
        import torch
        from ultralytics import YOLO

        report["torch"] = torch.__version__
        report["cuda_available"] = bool(torch.cuda.is_available())
        resolved = _write_resolved(data_yaml)
        model = YOLO(str(weights))

        data_cfg = yaml.safe_load(resolved.read_text(encoding="utf-8")) or {}
        data_names = data_cfg.get("names") or {}
        if isinstance(data_names, list):
            data_names = {i: n for i, n in enumerate(data_names)}
        model_names = getattr(model, "names", None) or {}
        report["model_names"] = {str(k): v for k, v in dict(model_names).items()}
        report["data_names"] = {str(k): v for k, v in dict(data_names).items()}

        if model_names and data_names:
            m_nc = len(model_names)
            d_nc = len(data_names)

            def _name_at(names: dict, idx: int) -> str:
                return str(names.get(idx, names.get(str(idx), ""))).strip()

            name_mismatch = any(
                _name_at(model_names, i) != _name_at(data_names, i)
                for i in range(min(m_nc, d_nc))
            )
            if m_nc != d_nc or name_mismatch:
                report["status"] = "BLOCKED"
                report["blocker"] = (
                    f"Checkpoint class taxonomy ({m_nc} classes: "
                    f"{list(dict(model_names).values())}) does not match "
                    f"data.yaml ({d_nc} classes: "
                    f"{list(dict(data_names).values())}). "
                    "Re-train on the current dataset, or evaluate with a "
                    "data.yaml / label set that matches the checkpoint."
                )
                out = outdir / "eval_report.json"
                out.write_text(json.dumps(report, indent=2), encoding="utf-8")
                print(json.dumps(report, indent=2))
                return 1

        # Guard Windows / redirected-stdout edge cases (NoneType.write)
        if sys.stdout is None:
            sys.stdout = io.StringIO()
        if sys.stderr is None:
            sys.stderr = io.StringIO()
        log_path = outdir / "eval_run.log"
        # plots=False avoids Ultralytics writer edge-cases on some Windows redirects
        metrics = model.val(
            data=str(resolved),
            imgsz=args.imgsz,
            batch=args.batch,
            device=args.device,
            split="val",
            plots=False,
            verbose=False,
            project=str(outdir),
            name="ufm_val",
            exist_ok=True,
            workers=0,
        )
        log_path.write_text(
            f"val completed for {weights}\ndata={resolved}\n",
            encoding="utf-8",
        )
        box = getattr(metrics, "box", None)
        per_class: dict[str, float] = {}
        names = getattr(metrics, "names", None) or getattr(model, "names", {}) or {}
        if box is not None:
            report["metrics"] = {
                "precision": float(getattr(box, "mp", 0) or 0),
                "recall": float(getattr(box, "mr", 0) or 0),
                "mAP50": float(getattr(box, "map50", 0) or 0),
                "mAP50_95": float(getattr(box, "map", 0) or 0),
            }
            maps = getattr(box, "maps", None)
            if maps is not None:
                for i, v in enumerate(list(maps)):
                    try:
                        key = int(i)
                    except Exception:  # noqa: BLE001
                        key = i
                    if isinstance(names, dict):
                        cname = names.get(key, names.get(str(key), str(key)))
                    else:
                        cname = str(key)
                    try:
                        per_class[str(cname)] = float(v)
                    except Exception:  # noqa: BLE001
                        continue
            report["metrics"]["per_class_mAP50_95"] = per_class
            # Also capture Ultralytics mean results if available
            try:
                report["metrics"]["results_dict"] = {
                    k: float(v)
                    for k, v in (getattr(metrics, "results_dict", {}) or {}).items()
                    if isinstance(v, (int, float))
                }
            except Exception:  # noqa: BLE001
                pass
        report["status"] = "MEASURED"
        report["ultralytics_save_dir"] = str(outdir / "ufm_val")
    except Exception as exc:  # noqa: BLE001
        report["status"] = "BLOCKED"
        report["blocker"] = f"{type(exc).__name__}: {exc}"

    out = outdir / "eval_report.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "MEASURED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
