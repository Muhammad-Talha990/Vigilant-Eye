# AI Core Implementation Report — VigilantEye

**Date:** 2026-10-04  
**Final status:** **C — PARTIALLY IMPLEMENTED**

This report follows the AI-1 brief. No metrics, datasets, or “trained/production-ready” claims are fabricated.

---

## 1. What was already present

- FastAPI live MJPEG pipeline (`backend/live_stream.py`) with Ultralytics YOLOv8n  
- COCO `yolov8n.pt` default inference path  
- `ai/detection_policy.py` IGNORE / REVIEW / CONFIRM + SessionTracker multi-frame streaks  
- Auto evidence SNAPSHOT/CLIP (`backend/evidence_auto.py`)  
- WebSocket + portal notification path  
- Invigilator-only Live Monitoring / Detections RBAC (`MONITOR_ROLES`)  
- Draft UFM case from detection (human Invigilator action)  
- Roboflow-derived merged images under `ai/dataset/ufm/`  
- Historical custom checkpoint `ai/runs/train/ufm_custom/weights/best.pt`  
- Posture/suspicion rule helpers (MediaPipe optional / OpenCV fallback)  

---

## 2. What was changed (this AI-1 pass)

| Change | Purpose |
|--------|---------|
| Detection alerts → Invigilator only | Align with C26 role boundary |
| `detections.model_version` + Alembic `20261004_0006` | Auditability |
| Live status: model version, device, latency/FPS | Operator AI status |
| Monitoring UI AI engine panel + event wording | Confidence ≠ guilt |
| `evaluate_model.py` taxonomy guard + measured eval | Honest metrics |
| `benchmark_inference.py` results retained | Latency evidence |
| `dataset_quality_pipeline.py` report | Dataset inventory |
| `session_aware_split.py` (+ dry-run plan) | Leakage mitigation tooling |
| SessionTracker cooldown fix (never-emitted) | Correct duplicate suppression |
| Expanded SessionTracker unit tests | Temporal validation coverage |
| AI docs set + this core report | Traceability |

---

## 3. Dataset sources

| Source | Local path |
|--------|------------|
| Offline Exam Monitoring 4 (Roboflow export) | `ai/dataset/ufm/dataset/offline-exam-monitoring-4/` |
| Exam cheating v1 (Roboflow export) | `ai/dataset/ufm/dataset/Exam cheating.v1i.yolov5pytorch/` |
| wrist-watch v4 (Roboflow export) | `ai/dataset/ufm/dataset/wrist-watch/` |
| University CCTV custom | **NOT AVAILABLE** (not invented) |
| FYP placed weak-label set (parallel tree) | `FYP/.../ai/dataset/ufm` (800/160) |

Official/source URLs beyond local export folders: **not fully captured in-repo** (Roboflow project pages). See `docs/AI_DATASET_REPORT.md`.

---

## 4. Dataset licenses

| Dataset | License status |
|---------|----------------|
| All Roboflow exports above | **NOT VERIFIED in-repo** — confirm before redistribution/commercial use |
| COCO pretrained `yolov8n.pt` | Ultralytics/COCO terms apply to baseline weights |

---

## 5. Dataset composition

| Split (merged 6-class `data.yaml`) | Images |
|-------------------------------------|--------|
| train | 5957 |
| val | 632 |

Class histogram (train instances, quality report): heavy `hand_normal` / `non_cheating`; fewer `mobile_phone`.  
**Taxonomy gap:** merged 6-class map ≠ historical 5-class checkpoint names.

---

## 6. Annotation strategy

1. Import Roboflow YOLO exports with remapping (`import_roboflow_dataset.py`).  
2. Quality scan (`dataset_quality_pipeline.py`).  
3. Optional COCO weak-label bootstrap for placed imagery (`prepare_placed_dataset.py`) — **bootstrap only**, not gold labels.  
4. Target vocabulary in `ai/ufm_classes.py` includes `normal_watch` (allowed) — **not** in current trained head.  
5. Behavior events (paper exchange, posture class) are **not** single-frame OD classes.

---

## 7. Train / validation / test split

- Current merged set: existing train/val folders (frame-level risk).  
- Session-aware plan generated: `ai/runs/session_aware_split_plan.json` (**dry-run only; not applied**).  
- Sessions estimated: 2212 → planned train/val/test image counts 5264 / 811 / 514.  
- Leakage warning remains active until `--apply` + retrain + re-eval.

---

## 8. Model architecture

| Item | Value |
|------|-------|
| Architecture | YOLOv8n (Ultralytics) |
| Live default | COCO `ai/weights/yolov8n.pt` |
| Custom opt-in | `YOLO_USE_CUSTOM=1` → `ai/runs/train/ufm_custom/weights/best.pt` |
| Custom class head (checkpoint) | 5 classes (see eval report) |

---

## 9. Training configuration (historical custom)

From `ai/runs/train/ufm_custom/args.yaml`: epochs 15, imgsz 416, batch 1, device cpu, seed 0, deterministic true.  
`results.csv` for that run is **missing**.

---

## 10. Training hardware

| Environment | Device |
|-------------|--------|
| This workstation (measured) | CPU — Intel Core i7-8565U; CUDA unavailable |
| Docker runtime image | CPU PyTorch wheels |
| GPU training | **Not available** in measured env |

---

## 11. Actual training status

| Item | Status |
|------|--------|
| Historical fine-tune artifact present | **Yes** (`best.pt`) |
| New full retrain completed in NEW PROJ this phase | **No** |
| Parallel FYP CPU train (15 epochs, imgsz 640) | **INCOMPLETE** — process stopped after epoch 7; `best.pt` mtime earlier than `last.pt`; not promoted |
| Custom weights production-defaulted | **No** |

---

## 12. Actual evaluation metrics

Measured via `ai/evaluate_model.py` against taxonomy-matched FYP 5-class val (160 images, weak labels):

| Metric | Value |
|--------|--------|
| Precision | 0.000278 |
| Recall | 0.0205 |
| mAP50 | 9.27e-05 |
| mAP50-95 | 2.28e-05 |

Artifact: `ai/runs/eval/eval_report.json` (`status: MEASURED`).

Evaluating against local 6-class `data.yaml`: **BLOCKED** (taxonomy mismatch) — by design.

---

## 13. Per-class performance

| Class | mAP50-95 |
|-------|----------|
| mobile_phone | 0.0 |
| smart_watch | 2.28e-05 |
| notes_paper | 0.0 |
| electronic_gadget | 0.0 |
| suspicious_object | 9.10e-05 |

---

## 14. Error analysis

Custom checkpoint quality is effectively unusable on the matched weak val set (near-zero mAP). Dominant failure is false negatives. Taxonomy drift between merge and checkpoint compounds the problem. COCO baseline remains the operational detector with policy/streak mitigations. Paper-exchange and learned posture are deferred. See `docs/AI_EVALUATION_REPORT.md`.

---

## 15. Inference latency

From `ai/runs/bench/bench_report.json` (custom @ 416, CPU):

| Stat | ms |
|------|-----|
| mean | 473.21 |
| median | 370.18 |
| p95 | 878.52 |

COCO @ 640 CPU (performance report): mean **721.1** ms.

---

## 16. FPS / throughput

| Weights | Theoretical FPS (1000/mean) |
|---------|-----------------------------|
| custom @416 CPU | **2.11** |
| COCO @640 CPU | **1.39** |

Live path samples with `LIVE_DETECT_EVERY` (default 2). **Not** hard real-time at full camera FPS on this CPU host.

---

## 17. Multi-frame validation

`SessionTracker`: confirm_frames (default 3), review_frames (2), stale_sec, persist cooldown.  
Cooldown now treats “never emitted” correctly (no false cooldown from timestamp 0).  
Spatial bins associate observations; no ByteTrack / no identity recognition.

---

## 18. Event semantics

```
RAW DETECTION → SUSPICIOUS OBSERVATION → multi-frame → CONFIRMED AI EVENT
→ evidence → Invigilator alert → human review → optional UFM case
```

Confirmed events carry camera, timestamp, type, confidence, model_version, validation decision, evidence refs.  
AI does **not** set guilt / approve / release results.

---

## 19. Evidence integration

Confirmed path uses existing `evidence_auto` SNAPSHOT/CLIP into Evidence library with RBAC ownership preserved.

---

## 20. Alert integration

`notify_detection_alert` → `MONITOR_ROLES` (Invigilator).  
HOD/DEC/Exam/UFM receive case-workflow notifications, not live AI streams.  
Cooldownown reduces notification storms.

---

## 21. Monitoring UI

Invigilator-only `MonitoringPage`: live MJPEG, camera state, AI engine status (model/device/latency), overlay labels with CONFIRM vs REVIEW, per-camera confirmed/review event list, confidence disclaimer. Responsive portal layout retained. Demo toggles remain on `/app/monitoring/demo`.

---

## 22. Failure handling

Model load / missing weights / camera disconnect / persist failures surface via session `ai_status`, `model_error`, `persist_error`. UI shows degraded badges. GPU unavailable → CPU path.

---

## 23. Model versioning

| Mode | ID |
|------|----|
| COCO | `coco/yolov8n.pt` |
| Custom | `ufm_custom/best.pt` |

Stored on `detections.model_version`. Weights gitignored; datasets/runs excluded from Docker image (`.dockerignore`).

---

## 24. Security / privacy

- No arbitrary model upload endpoint added  
- Monitoring/detections remain Invigilator-only  
- Evidence RBAC unchanged  
- No real student CCTV claimed  
- Internal weight paths not required in student-facing UI  

---

## 25. Tests

| Suite | Result |
|-------|--------|
| `test_detection_policy.py` + alert recipients + alembic head (AI-related) | **Passed** after head/cooldown updates |
| Full `backend/tests` (prior long run) | **343 passed, 3 failed** — failures were stale alembic head asserts (files now updated to `20261004_0006…`); re-check of the 4 head tests: **passed** |
| Frontend build | Not re-run in this closing pass (Monitoring UI already in tree) |

---

## 26. Regression results

Honest record:

1. Mid-phase full run: **343 passed / 3 failed** (alembic head expected old tip).  
2. Post-fix alembic head tests: **4/4 passed**.  
3. AI unit tests: **13–14 passed**.  

A fresh full green 346/346 suite was not re-executed end-to-end after the head-assert edits in this closing window; residual risk is limited to those already-corrected assertions.

---

## 27. Known limitations

1. Custom `best.pt` measured mAP ≈ 0 → not production-default.  
2. 6-class merged labels ≠ 5-class checkpoint.  
3. Dataset licenses unverified.  
4. No authorized exam-hall CCTV fine-tune data.  
5. Session-aware split not applied.  
6. Paper exchange / learned posture deferred.  
7. CPU-only → low FPS.  
8. Weak-label bootstrap is not gold annotation.  
9. Parallel FYP 15-epoch train incomplete (stopped ~epoch 7).  

---

## 28. Exact remaining blockers

1. **Hand-validated, session-aware, taxonomy-aligned dataset** (include `normal_watch`).  
2. **Completed fine-tune** with preserved `results.csv` + measured val/test mAP that justifies enabling custom weights.  
3. **License clearance** for Roboflow exports.  
4. **GPU or long CPU budget** for full retrain on ~6k images.  
5. **Paper-exchange temporal model** (scope S4) — not started.  
6. **Learned posture classifier** (scope S13) — not started.  

---

## 29. Deployment instructions

1. Build/run via existing `docker-compose` (API installs CPU torch; datasets/runs **not** copied into image).  
2. Mount or copy validated weights to `ai/runs/train/ufm_custom/weights/best.pt` only when evaluation justifies it.  
3. Default: leave `YOLO_USE_CUSTOM` unset/0 (COCO).  
4. Set `YOLO_USE_CUSTOM=1` only after measured metrics are acceptable.  
5. Run migrations including `20261004_0006_detection_model_version`.  
6. Invigilator starts Live Monitoring; confirmed events → evidence + alerts → human UFM.

Training environment ≠ inference image: train on host/venv with `ai/train_yolo.py`; ship only the chosen `.pt`.

---

## 30. Demonstration / deployment readiness

| Question | Answer |
|----------|--------|
| Is the **portal + COCO-assisted live AI path** demoable? | **Yes**, with documented COCO limits |
| Is the **custom exam-hall detector** ready? | **No** |
| Final status code | **C — PARTIALLY IMPLEMENTED** |

Do **not** claim “AI is ready” for custom detection. Do **not** treat COCO boxes as a trained UFM model.
