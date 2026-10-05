# AI Dataset Report — VigilantEye

**Status:** See authoritative gate in `docs/AI_DATASET_FORENSICS_REPORT.md` → **C — DATASET NOT READY**  
**Date:** 2026-10-04  
**Dataset versions:** placed CCTV+cheating videos (0 boxes); weak bootstrap experimental-only; Roboflow secondary exports in NEW PROJ

---

## 1. Detection taxonomy (object vs behavior)

### Object detection classes (YOLO)

| Class | Meaning | Why it matters | Type | Training requirement | Visual cues | Hard cases | FP risks | FN risks |
|-------|---------|----------------|------|---------------------|-------------|------------|----------|----------|
| `mobile_phone` | Smartphone / handset | Core prohibited item | Object | Required | Rectangular glowing/dark slab in hand/lap/desk | Under desk, pocket edge, phone-as-calc | Paper sheets, calculators | Occlusion, distance, glare |
| `smart_watch` | Smart wearable | Prohibited electronics | Object | Required (not in COCO) | Rectangular digital face on wrist | Vs analog watch, fitness band | Bracelets, phone edges | Tiny wrist ROI at CCTV distance |
| `normal_watch` | Ordinary wristwatch | **Allowed** hard-negative | Object | Required to cut FP | Round/analog or simple digital | Fashion watches vs smart | Mapping to smart_watch | Over-suppression of real smartwatches |
| `notes_paper` | Unauthorized notes / chits | Hidden notes | Object | Required | Small paper, folded sheets | Vs answer booklet / QP | Legitimate exam paper | Hidden in books, under thigh |
| `electronic_gadget` | Laptop / keyboard / mouse / similar | Prohibited electronics | Object | Partial via COCO | Larger devices | Calculators, allowed tools | Desk clutter | Partial views |
| `suspicious_object` | Ambiguous prop | Review bias | Object | Optional / high threshold | Bags, unknown handheld | Context-dependent | Over-alerting | Missed novel props |

### Behavior / temporal events (NOT one-frame classes)

| Event | Type | Training | Status |
|-------|------|----------|--------|
| Head / posture episode | Temporal + pose features | Sequence labels | Partial (rules / MediaPipe or OpenCV) |
| Paper exchange / peer interaction | Multi-actor temporal | Interval + actors | **Deferred — no trained model** |
| UFM guilt / discipline | Human workflow | N/A | **Never AI-autonomous** |

---

## 2. Datasets considered / used

### A. CCTV-Exam Monitor Dataset (placed)

| Field | Value |
|-------|--------|
| Name | CCTV-Exam -Monitor -Dataset |
| Path | `ai/dataset/ufm/dataset/CCTV-Exam -Monitor -Dataset/` (placed under FYP; prepare via `prepare_placed_dataset.py`) |
| Official URL | **NOT RECORDED in-repo** — user-placed export |
| License | **NOT VERIFIED** |
| Classes in export | Images only (no `.txt` labels observed at prepare time) |
| Size | train/valid/test image folders (capped to 800/160 for CPU train) |
| Characteristics | Exam-monitor style stills; CCTV-like angles preferred |
| Relevance | **High** for hall-like context |
| Limitations | Unlabeled → COCO weak-label bootstrap; may not match AU halls |
| Commercial/academic use | Unknown until license checked |
| Redistribution | Do **not** commit large binaries to Git |
| Fine-tune suitable | Bootstrap only until hand-labeled |
| Additional custom data | **Yes** required |

### B. Dataset_cheating (placed videos)

| Field | Value |
|-------|--------|
| Name | Dataset_cheating |
| Path | `ai/dataset/ufm/dataset/Dataset_cheating/` |
| License | **NOT VERIFIED** |
| Content | MOV/AVI (and similar) unlabeled videos |
| Prep | Frame extract every N frames, max frames/video; **video-level** train/val assignment |
| Relevance | Cheating behavior context — limited without labels |
| Limitations | Weak-labeled frames; domain shift |

### C. Offline Exam Monitoring 4 (Roboflow)

| Field | Value |
|-------|--------|
| Name | offline exam monitoring 4 — v6 |
| Source | Roboflow Universe export (local: `ai/dataset/ufm/dataset/offline-exam-monitoring-4/`) |
| Export date (file) | 2024-05-03 |
| Size (readme) | ~5676 images |
| Format | YOLOv8 |
| Relevance | Exam-monitoring / phone / cheating labels — **relevant** |
| License | **NOT VERIFIED in-repo** |
| Suitable for fine-tune | Yes as bootstrap, with class remapping |
| Limitations | Stretch resize; mixed scenes; may leak frames across splits |

### D. Exam cheating v1 (Roboflow)

| Field | Value |
|-------|--------|
| Name | Exam cheating — v1 |
| Source | `ai/dataset/ufm/dataset/Exam cheating.v1i.yolov5pytorch/` |
| Export date (file) | 2025-11-16 |
| Size (readme) | ~3407 images |
| Relevance | Exam cheating imagery — **relevant** |
| License | **NOT VERIFIED in-repo** |

### E. Wrist-watch (Roboflow)

| Field | Value |
|-------|--------|
| Name | wrist-watch — v4 |
| Source | `ai/dataset/ufm/dataset/wrist-watch/` |
| Relevance | Watch discrimination — useful for smart vs normal |
| License | **NOT VERIFIED in-repo** |
| Limitations | Close-up ≠ CCTV distance |

### F. University CCTV custom capture

| Field | Value |
|-------|--------|
| Status | **NOT AVAILABLE** — do not invent |
| Requirement | Authorized staged/exam-hall capture with privacy controls |
| Privacy | No real identifiable student footage without legal/ethical authorization |

---

## 3. Custom examination-hall data strategy

Required variation: camera angle, lighting, distance, density, seated students, occlusion, desks, hands, books/papers, phones, watches/devices, legitimate materials, negatives, difficult/FP examples.

**Privacy:** anonymize faces where policy requires; store outside Git; consent/authorization before any real exam recording.

---

## 4. Dataset quality pipeline

Script: `ai/dataset_quality_pipeline.py` → `ai/runs/dataset_quality.json`

Covers: counts, missing/orphan labels, corrupt images, class histogram, leakage warning.

Prep script: `ai/prepare_placed_dataset.py`

| Step | Handling |
|------|----------|
| Collection | Placed under `dataset/ufm/dataset/` |
| Dedup | Filename collision rewrite on copy |
| Annotation | COCO weak-label **or** import Roboflow |
| Validation | Quality pipeline + empty-label counts |
| Class consistency | Written `data.yaml` + `DATASET_VERSION.txt` |
| Split | CCTV folder split + video session-aware |
| Leakage | Avoid random frame split within same video |

---

## 5. Merged training sets

### Placed weak-label set (active fine-tune)

| Split | Images |
|-------|--------|
| train | 800 |
| val | 160 |

### Roboflow merge (NEW PROJ quality report)

| Split | Images |
|-------|--------|
| train | 5957 |
| val | 632 |

**Gap vs target taxonomy:** `normal_watch` often missing; placed COCO weak labels never create `smart_watch`.

---

## 6. Honesty

- Do not treat COCO weak labels as exam-hall ground truth.  
- Do not claim university CCTV data exists.  
- Do not redistribute datasets without license clearance.  
- Public datasets alone are insufficient for AU hall production claims.
