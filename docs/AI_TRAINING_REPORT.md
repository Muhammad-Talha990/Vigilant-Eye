# AI Training Report — VigilantEye

**Status:** PRIOR CHECKPOINT PRESENT + EVALUATED (poor); NEW FULL RETRAIN NOT COMPLETED IN THIS REPO  
**Date:** 2026-10-04  

---

## 1. Training pipeline

| Item | Path / command |
|------|----------------|
| Script | `ai/train_yolo.py` |
| Evaluate | `ai/evaluate_model.py` |
| Benchmark | `ai/benchmark_inference.py` |
| Quality | `ai/dataset_quality_pipeline.py` |
| Session split | `ai/session_aware_split.py` |
| Weak-label import | `ai/prepare_placed_dataset.py` |

Example (CPU / low RAM):

```powershell
python ai/dataset_quality_pipeline.py
python ai/session_aware_split.py --dry-run --source-split all
python ai/train_yolo.py --epochs 15 --batch 1 --imgsz 416 --mosaic 0 --workers 0 --device cpu
python ai/evaluate_model.py --weights ai/runs/train/ufm_custom/weights/best.pt --imgsz 416 --device cpu
```

---

## 2. Checkpoint on disk (this repo)

| Field | Value |
|-------|--------|
| Checkpoint | `ai/runs/train/ufm_custom/weights/best.pt` (~6.25 MB) |
| Also | `last.pt` |
| Architecture | YOLOv8n (Ultralytics) |
| Pretrained start | `yolov8n.pt` |
| Epochs (args.yaml) | 15 |
| imgsz | 416 |
| batch | 1 |
| device | cpu |
| seed | 0 |
| deterministic | true |
| Class names in weights | mobile_phone, smart_watch, notes_paper, electronic_gadget, suspicious_object |
| results.csv | **MISSING** in this run directory |

---

## 3. Actual training status

| Question | Answer |
|----------|--------|
| Did fine-tuning run historically? | **Yes** — checkpoint + Ultralytics plots exist |
| Are numeric mAP/P/R from that run preserved in CSV? | **No** |
| Was a new full retrain completed in NEW PROJ this phase? | **No** |
| Measured post-hoc val metrics? | **Yes** — see `AI_EVALUATION_REPORT.md` (near-zero mAP) |
| Is custom default in live inference? | **No** — COCO default; `YOLO_USE_CUSTOM=1` opt-in only |

---

## 4. Parallel FYP train (not merged as production)

| Field | Value |
|-------|--------|
| Location | `C:\Users\KING\Desktop\FYP\Vigilant Eye` |
| Command | `python -u ai/train_yolo.py --epochs 15 --batch 4 --imgsz 640 --name ufm_custom --device cpu` |
| Data | Placed CCTV + Dataset_cheating, COCO-weak labels, 800 train / 160 val |
| Status at report time | **IN PROGRESS** (results through epoch 10) |
| Epoch 5 (best so far on curve) | P=0.565, R=0.194, mAP50=0.243, mAP50-95=0.169 |
| Epoch 8 | P=0.669, R=0.146, mAP50=0.181, mAP50-95=0.108 |
| Epoch 9 | P=0.577, R=0.038, mAP50=0.172, mAP50-95=0.134 |
| Epoch 10 | P=0.681, R=0.191, mAP50=0.179, mAP50-95=0.137 |

These numbers are **training-curve snapshots on COCO weak labels**, not a completed final evaluation for this portal. Sync into NEW PROJ with `scripts/sync_placed_train_artifacts.ps1` after epoch 15.

---

## 5. Model version identity

| Mode | Identifier |
|------|------------|
| COCO baseline | `coco/yolov8n.pt` |
| Custom checkpoint | `ufm_custom/best.pt` |

Persisted on `detections.model_version` (Alembic `20261004_0006_detection_model_version`).

---

## 6. Hardware / software (measured env)

Python 3.14.3 / torch 2.13.0+cpu / ultralytics 8.4.126 / CUDA unavailable / Intel Core i7-8565U.

---

## 7. Blockers for production custom model

1. Measured mAP of existing `best.pt` is unusable on matched val.  
2. Local merged Roboflow set uses a **different 6-class map** than the checkpoint.  
3. `normal_watch` still missing from trained heads.  
4. No authorized local CCTV fine-tune set.  
5. Session-aware split planned (`session_aware_split_plan.json`) but **not applied**.  
6. Paper-exchange / learned posture models not trained.  
7. GPU unavailable — full retrain on 5.9k images is multi-hour/day on CPU.
