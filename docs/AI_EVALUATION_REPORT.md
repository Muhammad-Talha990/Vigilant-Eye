# AI Evaluation Report — VigilantEye

**Status:** MEASURED (with documented limitations)  
**Date:** 2026-10-04  

---

## 1. Protocol

```powershell
python ai/evaluate_model.py --weights ai/runs/train/ufm_custom/weights/best.pt --imgsz 416 --batch 1 --device cpu
```

Output: `ai/runs/eval/eval_report.json`

Evaluator now **fails fast** when checkpoint class names ≠ `data.yaml` names (prevents opaque Ultralytics `KeyError`).

---

## 2. Taxonomy mismatch (local merged set)

| Artifact | Classes |
|----------|---------|
| `ai/runs/train/ufm_custom/weights/best.pt` | 5: mobile_phone, smart_watch, notes_paper, electronic_gadget, suspicious_object |
| `ai/dataset/ufm/data.yaml` (merged Roboflow) | 6: mobile_phone, smart_watch, notes_paper, suspicious_object, non_cheating, hand_normal |

Evaluating the checkpoint against the 6-class `data.yaml` is **BLOCKED** (correctly).  
Target 5-class map documented in `ai/dataset/ufm/data_5cls_target.yaml`.

---

## 3. Measured results (taxonomy-matched val)

**Command used:** evaluate `best.pt` with FYP placed 5-class `data.yaml` (160 val images; COCO-weak labels).

| Metric | Value |
|--------|--------|
| Precision | **0.000278** |
| Recall | **0.0205** |
| mAP50 | **9.27e-05** |
| mAP50-95 | **2.28e-05** |

### Per-class mAP50-95

| Class | mAP50-95 |
|-------|----------|
| mobile_phone | 0.0 |
| smart_watch | 2.28e-05 |
| notes_paper | 0.0 |
| electronic_gadget | 0.0 |
| suspicious_object | 9.10e-05 |

**Hardware:** Windows 10, Intel Core i7-8565U, Python 3.14.3, torch 2.13.0+cpu, CUDA unavailable, Ultralytics 8.4.126.  
**Val speed (this run):** ~801 ms inference / image @ imgsz 416.

### Interpretation (honest)

These numbers are **not** production-grade. The historical custom checkpoint does **not** generalize to the weak-labeled placed val set. Live default must remain **COCO `yolov8n.pt`** unless/until a new train+eval cycle produces usable metrics on a correctly labeled, session-aware split.

Caveats that further limit interpretation:

1. Val labels are COCO-weak-bootstrapped (circular / noisy).  
2. 160 images only.  
3. No authorized university CCTV hold-out.  
4. Possible optimistic leakage risk on other merges (see session-aware split plan).

---

## 4. Error analysis (qualitative + metric-driven)

| Failure mode | Evidence |
|--------------|----------|
| Near-zero detection quality | Measured mAP ≈ 0 on matched taxonomy val |
| False negatives | Dominates (recall 0.02) |
| Custom empty/weak preds on real samples | Consistent with code comments / live default = COCO |
| Taxonomy drift | 6-class merge ≠ 5-class checkpoint |
| Paper exchange / posture DL | Not evaluated — models not trained |
| Legitimate materials | COCO `book`→notes remains REVIEW-only by policy |

**Conclusion:** Another fine-tuning cycle is **required** on a corrected, hand-validated, session-aware dataset before custom weights can be production-defaulted. Do not enable `YOLO_USE_CUSTOM=1` for demo reliability based on this checkpoint.

---

## 5. In-progress parallel train (FYP placed set)

A separate CPU train (`--epochs 15 --batch 4 --imgsz 640`) was still running on the FYP tree with partial `results.csv` through epoch 5 (mAP50 ≈ 0.24 on its own weak-label val). That run is **not** accepted as final until it completes and is re-evaluated with `evaluate_model.py` after copy into this repo. Partial epoch rows must not be reported as final test metrics.
