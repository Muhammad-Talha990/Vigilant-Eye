# C19 — AI Architecture & Implementation Plan

**Document type:** Planning + architecture blueprint only  
**Date:** 2026-10-03 (expanded blueprint revision)  
**Code changes in this phase:** **NONE**  
**Authoritative AI source:** `VigilantEye Scope Document.pdf`  
**Supporting sources:** `VigilantEye_Master_Cursor_Development_Learning_Protocol.md`, `docs/REQUIREMENTS_TRACEABILITY.md`, `docs/SCOPE_COVERAGE.md`, repository inspection  

**How to read “scope vs engineering”**

| Tag | Meaning |
|-----|---------|
| **[SCOPE]** | Explicitly required or described by the Scope Document |
| **[PROJECT]** | Explicit current project decision (may constrain Scope UI items) |
| **[ENGINEERING]** | Architecture/model not prescribed by scope — requires selection during implementation |
| **[REPO]** | Observed in the current repository |

---

## 1. Executive Summary

VigilantEye’s AI layer is a **local, institutional CCTV monitoring assistant** for physical examination halls. Per the Scope Document it combines:

1. **YOLO-based object detection** (Tools: YOLOv8) for prohibited/suspicious objects.  
2. **MediaPipe-based pose/behavior feature extraction** plus a **custom classifier on derived angles** (Correct / Incorrect posture).  
3. **Temporal / multi-frame validation** before treating activity as a confirmed monitoring event.  
4. **Automatic evidence** (short clip + snapshots + metadata) and **real-time alerts** to Invigilator/HOD monitoring surfaces.  
5. Optional human creation of UFM cases that then follow the **existing** portal workflow.

**What AI is:** detect → validate over time → package evidence → alert authorized monitors.  
**What AI is not:** an autonomous disciplinary decision-maker. HOD / DEC / Exam / UFM Committee / student clarification / result-control remain authoritative **[PROJECT + institutional workflow]**.

**Today [REPO]:** a **COCO-pretrained YOLOv8n** live path exists with policy/streaks, rule-based posture/suspicion, auto evidence, and WebSocket alerts. **Custom exam-hall YOLO weights, learned posture classifier, and paper-exchange detection are not production capabilities** — they are deferred to later AI phases.

**C19 delivers:** this blueprint only. No training, no weights, no schema/RBAC/UI/workflow changes.

---

## 2. Current AI/CV State

### 2.1 Classification of today’s components

| Component | Classification | Evidence |
|-----------|----------------|----------|
| OpenCV capture / MJPEG / RTSP/file/webcam | **Already implemented** | `backend/live_stream.py`, `routers/live.py` |
| Ultralytics YOLOv8 dependency | **Already implemented** (runtime baseline) | `requirements.txt` `ultralytics==8.4.126`; live `predict` |
| COCO `yolov8n.pt` path / download-on-first-use | **Baseline integrated** | `ai/ufm_classes.py` `default_coco_weights()`; `.pt` gitignored (often absent in tree) |
| Custom `best.pt` + `YOLO_USE_CUSTOM` | **Baseline/dependency present; not production-default** | Path + flag exist; custom file usually missing; default is COCO |
| Detection policy IGNORE/REVIEW/CONFIRM + COCO exclusions | **Already implemented** | `ai/detection_policy.py` |
| Multi-frame streaks / cooldown (SessionTracker) | **Partially implemented** | Works; some `UFM_*` env vars not fully wired into live `start()` |
| Auto SNAPSHOT + CLIP (WebP) | **Already implemented** (with limits) | `backend/evidence_auto.py` |
| WebSocket alerts + HOD notifications | **Already implemented** | `ws_alerts.py`, `detection_bridge.py`, AppLayout |
| Draft case from detection | **Already implemented** | `POST /detections/{id}/create-draft-case` (INVIGILATOR) |
| MediaPipe FaceMesh (optional) | **Partially implemented** | `ai/posture_analysis.py`; **not** in `requirements.txt`; OpenCV fallback |
| Rule-based suspicion / head yaw-pitch | **Already implemented** (provisional thresholds) | `ai/suspicion_score.py` |
| Learned Correct/Incorrect posture model | **Not implemented / Deferred** | `ai/posture_model_README.md` |
| Paper-exchange / peer-interaction model | **Not implemented / Deferred** | Traceability R18 |
| Custom chit/watch training in production | **Required by scope but still missing / Deferred** | Scope §7; R02/R18 |
| YOLO multi-object tracker (ByteTrack etc.) | **Not implemented** | Spatial bins only |
| Seat-map visualization | **Excluded [PROJECT]** | Traceability R19 |

### 2.2 Capability honesty (do not confuse package ≠ feature)

| Capability | Honest status |
|------------|---------------|
| “YOLO works” | **Yes** as COCO baseline inference in live loop when weights load |
| “Exam-hall UFM detector complete” | **No** — smartwatch/normal_watch/chits not COCO-native |
| “MediaPipe behavior system complete” | **No** — optional feature extract + rules; no learned classifier |
| “Paper exchange detection” | **No** |
| “AI convicts / auto-approves UFM” | **Must never** — and currently does not |

### 2.3 Live OD configuration observed [REPO]

| Parameter | Value |
|-----------|--------|
| Default weights | COCO yolov8n (`ai/weights/yolov8n.pt`) |
| Custom weights | `ai/runs/train/ufm_custom/weights/best.pt` if `YOLO_USE_CUSTOM=1` |
| Filtered COCO IDs | 63,64,66,67,73 (laptop, mouse, keyboard, cell phone, book) |
| Inference size | `LIVE_IMGSZ` default 640 |
| Detect cadence | every `LIVE_DETECT_EVERY` (default 2) loops |
| Device | Docker forces CPU PyTorch; `YOLO_DEVICE=cpu` in Dockerfile **not read by app code** |
| Tracking | No Ultralytics tracker; spatial bin keys |

---

## 3. Scope-Derived AI Requirements

From `VigilantEye Scope Document.pdf` (not invented):

| ID | Requirement | Scope locus |
|----|-------------|-------------|
| S1 | Physical exam halls; CCTV/IP; institutional control rooms | §5 |
| S2 | No external cloud surveillance dependency | §5 |
| S3 | YOLO-based object detection (Tools: **YOLOv8**) | §6.1, §8 |
| S4 | Detect: mobile phones, smart watches, electronic gadgets, hidden notes, paper exchange, suspicious hand/head movement, peer interaction | §4, §6.1 |
| S5 | Multi-frame consistency before confirming event | §5.1, §6.1 |
| S6 | Confidence + timestamp on detections | §6.1 |
| S7 | Real-time alerts to Invigilator & HOD monitoring | §6.1, §6.5 |
| S8 | Auto short video clip + key snapshots + camera/room/(seat if mapped)/confidence metadata | §6.2 |
| S9 | Manual evidence alongside AI evidence; link to cases | §6.2 |
| S10 | Public CV datasets + custom controlled CCTV; fine-tune YOLO | §7 |
| S11 | Annotated exam scenarios for behavior + alert validation | §7 |
| S12 | MediaPipe for behavior/pose | §8 |
| S13 | Custom DL on MediaPipe-derived angles → Correct / Incorrect posture | §8 |
| S14 | OpenCV, WebSocket, FastAPI, React, Postgres, Docker, RTSP | §8 |
| S15 | End-to-end UFM portal (human workflow) | §6.3–6.6 |

**Not prescribed by Scope (must not be pretended):** exact YOLO nano/small/medium variant for production; exact tracker algorithm; exact posture network family (MLP/LSTM/…); exact FPS targets; exact dataset sizes; seat-map as mandatory UI (**[PROJECT] excludes seat-map visualization**).

---

## 4. Complete AI Architecture

Adapted to **this** repository (live inference today lives inside the API process via `LiveStreamManager`, not a separate microservice).

```text
CCTV / IP / RTSP / file / webcam
        ↓
OpenCV Frame Ingestion (+ reconnect / freeze detection — harden later)
        ↓
Frame Sampling / Preprocessing (detect_every, imgsz, quality gates)
        ↓
YOLO Object Detection (COCO baseline → custom exam-hall weights when validated)
        ↓
Person / Object Association (spatial bins today → optional tracker [ENGINEERING])
        ↓
Behavior / Pose Analysis (MediaPipe or OpenCV fallback → angles → rules; later learned classifier)
        ↓
Temporal / Multi-Frame Validation (SessionTracker + configurable params)
        ↓
AI Event Classification (RAW → OBSERVATION → CANDIDATE → CONFIRMED AI EVENT)
        ↓
Confidence + Timestamp + Camera + Model Version
        ↓
Evidence Capture (reuse evidence_auto → Evidence library)
        ↓
Real-Time Alert (WebSocket + portal notifications; MONITOR roles only)
        ↓
Monitoring Dashboard (Invigilator / HOD / Exam Dept per RBAC)
        ↓
Human Review
        ↓
Optional UFM Case → Existing Case Workflow (unchanged)
```

### Event ladder (mandatory semantics)

```text
RAW DETECTION
    ↓  (persistence / policy)
SUSPICIOUS OBSERVATION
    ↓  (temporal validation)
CANDIDATE AI EVENT
    ↓  (configured event rules / cooldown)
CONFIRMED AI EVENT
    ↓  (evidence + alert)
HUMAN REVIEW
    ↓
UFM DECISION (portal workflow only)
```

**Deterministic application logic (not “AI”):** RBAC, case lifecycle, sign-off, notifications on case status, result hold on APPROVE, audit trail, evidence access control.

**AI / CV logic:** models, features, temporal validators that propose monitoring events.

---

## 5. Model-by-Model Architecture

| Task | Model | Input | Output | Training data | Annotation | Training method | Inference | Validation | Confidence | Temporal | Status | Phase |
|------|-------|-------|--------|---------------|------------|-----------------|-----------|------------|------------|----------|--------|-------|
| Prohibited object detection | **YOLOv8 family** (Ultralytics) **[SCOPE]**; start from pretrained YOLO checkpoint | RGB frame (imgsz configurable) | Boxes, class, score | Public + custom exam CCTV **[SCOPE §7]** | YOLO boxes | Fine-tune **[SCOPE]** | Live `predict` in `live_stream` | Held-out sessions; mAP/P/R | Per-class review/confirm gates | Streaks / window | **Baseline COCO**; custom **deferred** | AI-2, AI-3 |
| Allowed-class disambiguation (e.g. normal_watch) | Same custom YOLO head | Frame | `normal_watch` (no UFM) | Hard negatives | Boxes | Same train run | Same | Per-class FP analysis | High bar before any map to smart_watch | Same | **Missing weights** | AI-2 |
| Pose / landmark extract | **MediaPipe** **[SCOPE]**; OpenCV fallback **[REPO]** | Frame / face ROI | Landmarks → yaw/pitch/roll | N/A (pretrained MP) | N/A | N/A | Every N frames | Estimator quality flags | Quality gating | Episode duration | **Partial** | AI-6 |
| Posture Correct/Incorrect | Custom DL on **angles** **[SCOPE]**; **architecture not prescribed** | Feature sequences | Correct / Incorrect (+ score) | Human-labeled sequences | Sequence labels | Train after data exists | Gated alongside rules | Confusion matrix vs rules | Classifier score ≠ UFM guilt | Multi-frame | **Deferred** | AI-7 |
| Suspicion scoring | Rule engine **[REPO]** | Objects + head episodes | Score / level | Calibration footage | Event labels | Threshold tuning | Live | Event-level FP/FN | Explicit contributors | Decay + cooldown | **Implemented (provisional)** | AI-1, AI-9 |
| Paper exchange / peer interaction | **Not prescribed** beyond problem statement **[SCOPE lists activity]** | Tracks + pose + paper cues over time | Candidate exchange event | Temporal segments | Interval + actors | **[ENGINEERING]** after data | Offline→live | Event P/R | Episode score | Required | **Deferred** | AI-8 |
| Association / tracking | **Not prescribed** **[ENGINEERING]** | Detections over time | track_id / links | MOT-style optional | Optional IDs | Eval trackers | Live | ID switches / FP links | Association confidence | Continuity | Spatial bins only | AI-4 |

---

## 6. YOLO Model Selection Strategy

### 6.1 Why YOLO

**[SCOPE]** Tools table names **YOLOv8** for AI-based UFM object detection. **[REPO]** already uses Ultralytics YOLOv8. Master protocol also specifies YOLO/Ultralytics.

### 6.2 COCO vs custom examination-hall model

| Mode | Role |
|------|------|
| Pretrained COCO (`yolov8n`) | **Development / demo baseline** — phones/books/laptops only as proxies |
| Fine-tuned custom weights | **Target university detector** for classes COCO lacks or misrepresents (smartwatch, normal_watch, chits, exam-specific phones) |

**Final system must not rely only on generic COCO** if required classes are not adequately represented **[SCOPE §7 + engineering necessity]**.

### 6.3 Candidate variants (selection deferred to benchmarking)

| Candidate | Typical tradeoff | When to consider |
|-----------|------------------|------------------|
| YOLOv8n | Fastest, lowest accuracy | CPU-only demo / many cameras / low VRAM |
| YOLOv8s | Balance | Likely first custom-train candidate on modest GPU |
| YOLOv8m+ | Higher accuracy, slower | If hall density/occlusion demands it and hardware allows |

**Exact final variant is [ENGINEERING]** — choose after measuring: GPU/CPU, FPS, resolution, camera count, latency, accuracy on held-out hall footage, Docker CPU constraint.

### 6.4 Proposed target classes (derived from Scope + existing `ufm_classes.py`)

| Class | Why (scope) | Annotation | Difficulty | False positives | OD alone enough? |
|-------|-------------|------------|------------|-----------------|------------------|
| `mobile_phone` | Explicit | Box on device | Medium (occlusion, pocket) | Calculators, remotes, watch faces | **No** — need persistence + context |
| `smart_watch` | Explicit | Box on wearable | Hard (small, similar to watches) | Normal watches, bracelets | **No** |
| `normal_watch` | Needed to stop watch↔phone/smart confusion **[REPO policy]** | Box; **non-UFM** | Hard | Mislabel as smart_watch | Prevents false UFM |
| `notes_paper` / cheating material | Hidden notes **[SCOPE]** | Box on slip/sheet | Hard (desk paper, answer sheets) | Blank sheets, question papers | **No** — exchange needs temporal model |
| `electronic_gadget` | Explicit | Box (define subclass list in dataset card) | Medium | Keyboards, allowed devices | **No** |
| `person` (optional) | Association support **[ENGINEERING]** | Box or use detector person class | Medium | Crowding | Enables association; not a UFM class alone |
| `suspicious_object` | Catch-all **[REPO]** | Use sparingly | High ambiguity | Everything unusual | Prefer avoid; REVIEW-only if used |

Do **not** add unrelated classes “because useful.” Expand only with dataset card justification.

---

## 7. YOLO Training Pipeline

**Do not train in C19.** Lifecycle for AI-2+:

1. Collect public datasets (license-checked).  
2. Collect controlled custom exam-hall / lab CCTV.  
3. Ensure realism: angles, lighting, seating density, distance, occlusion, clothing, device/paper appearance.  
4. Annotate required objects (YOLO format).  
5. Annotation QA (spot checks, dual-label sample).  
6. Split by **session/camera/setup** (not random adjacent frames).  
7. Fine-tune from pretrained YOLO checkpoint via `ai/train_yolo.py` (extend as needed).  
8. Validate → error analysis → tune → final test → version artifact → optional staged enable (`YOLO_USE_CUSTOM=1`).

### Training details

| Topic | Plan |
|-------|------|
| Annotation format | Ultralytics YOLO txt + `data.yaml` **[REPO scripts]** |
| Class IDs | Stable map in dataset YAML aligned to `UFM_CLASS_NAMES` |
| Resolution | Train multi-scale; infer at `LIVE_IMGSZ` (default 640) — tune later |
| Augmentation | Mosaic/flip/color/blur as Ultralytics defaults + exam-specific dark/bright — **tune at implementation** |
| Pretrained checkpoint | YOLO pretrained (COCO) as start **[SCOPE fine-tune]** |
| Epochs / batch / LR / early stop | **Implementation-time tuning parameters** — not invented here |
| Experiment tracking | Run dir under `ai/runs/train/...` + metadata JSON |
| Versioning | See §24 |

---

## 8. Dataset Collection & Annotation Plan

### 8.1 Object detection dataset

| Field | Plan |
|-------|------|
| Sources | Public (license per set) + custom institutional/lab **[SCOPE §7]** |
| Quantity | **To be determined after pilot collection** — start with pilot sessions, expand until val metrics stabilize |
| Conditions | Overhead/side CCTV-like; day/artificial light; near/far; occlusion; multi-student |
| Balance | Oversample rare classes (smartwatch, chits); include many **negatives** |
| Difficult examples | Partial phones, watches under sleeve, folded notes, glare |
| Negatives | Empty desks, allowed stationery, normal watches, reading question paper |
| Annotation | Boxes; tool TBD **[ENGINEERING]** (e.g. CVAT/Label Studio/Roboflow) |
| QA | Inter-annotator sample; reject ambiguous without guidelines |
| Split | By recording/session/camera |
| Leakage | No near-duplicate frames across splits |
| Versioning | `dataset_version`, manifest of videos, license file |
| Storage | Local institutional storage; not public git for identifiable faces if policy forbids |
| Privacy | Consent + university policy **[policy, not invented here]** |

### 8.2 Behavior / posture dataset

Include **normal** writing/looking down, **suspicious-looking but legitimate** behavior, **genuine** target behavior, and **ambiguous** cases labeled conservatively. Labels must be **human**, not auto-copied from rule thresholds alone (circularity).

### 8.3 Paper-exchange dataset

Temporal segments with start/end, actor ids if possible, and negative proximity without exchange. Quantity TBD after pilot.

---

## 9. Train / Validation / Test Strategy

| Split | Purpose | Rule |
|-------|---------|------|
| Train | Learn weights / fit classifier | Majority of sessions |
| Validation | Epoch selection, threshold tuning | Disjoint sessions |
| Test | Final unbiased report | Held-out sessions/halls never used for tuning |

**Critical:** Do **not** randomly split adjacent frames. Split by recording/session (and camera/setup where possible) so test ≈ unseen footage.

Report metrics on **test** only after freezing thresholds chosen on **validation**.

---

## 10. Person / Object Association

### 10.1 Current [REPO]

- No ByteTrack/BoT-SORT/etc.  
- Object streaks keyed by spatial bin (`category@bin`).  
- Face/head observations use lightweight track ids in posture path.  
- Traceability R20: candidate track IDs **partial**.

### 10.2 Why association is needed

Detecting a phone in empty aisle ≠ attributing to a candidate. Exchange requires **person ↔ person** and **person ↔ paper** over time.

### 10.3 Options [ENGINEERING — evaluate, do not pick in C19]

| Option | Pros | Cons |
|--------|------|------|
| Keep spatial bins | Simple, already integrated | Unstable under motion |
| Ultralytics built-in trackers | Easy with YOLO | Needs eval on hall density |
| External ByteTrack / BoT-SORT | Strong MOT ecosystem | Extra dependency/ops |
| Detection-only + short-term IoU matching | Lightweight | Weak under occlusion |

**Selection criteria:** ID switch rate, association precision for phone↔person, CPU cost, occlusion behavior, integration with existing `SessionTracker`.

### 10.4 Design notes

- Persist IDs across frames until stale timeout.  
- On occlusion: freeze or mark `association_uncertain` → prefer REVIEW not CONFIRM.  
- Reduce false links via IoU/distance gates + class priors (phone near hand/torso).

---

## 11. MediaPipe + Behavior Architecture

```text
Camera frame
    ↓
Person / face region (detector or MP)
    ↓
MediaPipe landmarks  [SCOPE]
    ↓
Derived features / angles  [SCOPE]
    ↓
Rule baseline (today)  AND/OR  posture classifier (deferred)
    ↓
Temporal validation
    ↓
AI observation / event
```

**MediaPipe = feature extraction layer**, not automatically the final UFM classifier.

**[REPO]** FaceMesh when import works; else OpenCV Haar + solvePnP labeled `opencv_fallback` (not precise gaze).

Hand movement is listed in Scope §6.1 but **hand landmark pipeline is not implemented** — treat as extension under AI-6/AI-8 after face/posture path is stable.

---

## 12. Posture Classifier Plan

**[SCOPE]** Custom deep-learning models analyze MediaPipe-derived angles → **"Correct" or "Incorrect"**.

**Classifier architecture is not prescribed by scope.**  
**Statement:** *Classifier architecture will be selected after dataset and feature evaluation.* **[ENGINEERING]**

Before choosing MLP vs sequence model vs other:

1. Collect labeled sequences (angles, dt, quality, estimator).  
2. Measure class balance and temporal length of episodes.  
3. Baseline with rules (`suspicion_score`).  
4. Try simplest model that beats rules on held-out data without circular labels.  
5. Only then gate into production behind a feature flag.

**Do not replace working rules automatically.** Compare side-by-side; adopt only if justified.

---

## 13. Paper-Exchange / Peer-Interaction Plan

**Temporal behavior problem**, not `paper = cheating`.

| State | Meaning |
|-------|---------|
| Paper visible | OD `notes_paper` / proxy |
| Paper being moved | Motion of paper/hand cues over frames |
| Paper exchange between candidates | Two-person proximity + coordinated transfer + temporal persistence |

**Combine [ENGINEERING design]:** person positions, pose/hand movement, paper detection, neighbor relationships, multi-frame persistence.

**Exact model architecture not specified by Scope** — state so explicitly. Data: temporal segments, negatives (sitting close without exchange), ambiguous cases → REVIEW.

**Deferred** to AI-8 per project decision.

---

## 14. Multi-Frame Validation

**[SCOPE]** Repeated/consistency validation before final alert/evidence.

**[REPO]** `SessionTracker`: confirm/review frame counts, stale reset, cooldown (~45s hardcoded in live start; env partially unused).

### Tunable engineering parameters (values empirical later)

| Parameter | Role |
|-----------|------|
| Minimum persistence (frames or seconds) | Avoid one-frame noise |
| Confidence aggregation (mean/max/p50) | Stabilize scores |
| Window length | Rolling confirmation |
| Cooldown | Duplicate suppression |
| Event reset / stale | Incomplete streaks die |
| Intermittent detection handling | Allow small gaps inside window **[ENGINEERING]** |

**Example numbers in prose are illustrative only — do not hard-code as production truth.**

---

## 15. Confidence & Event Semantics

| Stage | Meaning | Confidence | Persist | Alert | Case |
|-------|---------|------------|---------|-------|------|
| **Raw Detection** | Single-frame model output | Model score | Debug optional | No | No |
| **Suspicious Observation** | Persists / REVIEW policy | Aggregate | Candidate (`is_confirmed=false`) + optional snap | Soft/none | No |
| **Candidate AI Event** | Temporal validation passed pending final rules | Aggregate + rules | Yes | Optional | No |
| **Confirmed AI Event** | Configured AI event rules passed | Stored with event | Detection + evidence | Yes (monitor roles) | Human optional |
| **Human-reviewed UFM Case** | Staff decision in portal | N/A (institution) | Case + linked evidence | Workflow notifies | Yes |

Always store when elevating: timestamp, camera, model version, validation_state, event_type, evidence refs.

---

## 16. Evidence Capture Architecture

**Reuse existing library** — do not build a parallel vault.

| Piece | Today | Plan |
|-------|-------|------|
| Snapshot JPEG | Yes | Keep |
| Short clip | Animated WebP from ~16 buffer frames on confirm | Document format; optional pre/post rings later |
| Metadata | camera_id, confidence, timestamp, detection_id | Enrich room via camera join; seat only if already in data — **no seat-map UI** |
| Manual upload | Yes | Coexist |
| Case link | Draft/create attaches orphans | Unchanged workflow |

**Entry point:** Confirmed persist in `live_stream` → `evidence_auto.create_detection_evidence` → `Evidence` rows → optional Invigilator case.

---

## 17. Alert Architecture

```text
Confirmed AI Event
    ↓
Alert service (detection_bridge + ws_hub)
    ↓
WebSocket /ws/alerts + portal notification rows
    ↓
Authorized monitoring users (INVIGILATOR, HOD, EXAM_DEPARTMENT)
    ↓
Dashboard / banner
    ↓
Human review
```

Preserve RBAC: DEC / UFM Committee / Student / Admin do **not** gain live detection feeds merely because AI exists.

Do **not** send final disciplinary “AI verdict” notifications from the inference loop.

---

## 18. AI → UFM Integration

```text
AI event → Evidence package → Authorized human review → Existing case workflow
```

AI **must not:** auto-convict; auto-APPROVE/REJECT; auto result-hold; bypass HOD/DEC/Exam/UFM; bypass student clarification; bypass C16 result-control.

AI **may:** create monitoring detections, attach evidence, notify monitors, help Invigilator draft a case.

---

## 19. Human-in-the-Loop Boundaries

| Layer | Owner |
|-------|--------|
| Pixel/model outputs | AI |
| Temporal confirmation config | Engineering + validation data |
| “Is this worth a case?” | Invigilator / HOD monitoring judgment |
| Case truth & sanctions | Institutional workflow roles |
| Result hold | Existing APPROVE path only |

---

## 20. Evaluation Metrics

**Object detection:** precision, recall, mAP, per-class, error analysis, latency/FPS.  
**Behavior classification:** precision, recall, F1, confusion matrix, FP/FN rates.  
**Event validation:** event-level P/R, duplicate-event rate, false-alert rate, alert latency.  
**Evidence pipeline:** capture success rate, timestamp correctness, failure rate.

**Acceptance criteria:** set during AI implementation/testing — **no fabricated target scores** (Scope does not prescribe numeric targets).

---

## 21. False-Positive Reduction

Do **not** rely on confidence threshold alone — exam halls are noisy; COCO proxies are wrong often.

**Layers:**

1. Model confidence threshold  
2. Class-specific thresholds (justified by val data)  
3. Multi-frame persistence  
4. Temporal smoothing / aggregation  
5. Person/object association quality gates  
6. Contextual rules (e.g. COCO book → never auto-CONFIRM **[REPO]**)  
7. Duplicate suppression  
8. Cooldown  
9. **Human review** before institutional consequences  

Why thresholds alone fail: single-frame glare/occlusion and systematic class confusion (watch↔phone) survive any single cutoff.

---

## 22. Performance / Hardware Plan

| Item | Known | Plan |
|------|-------|------|
| Dev baseline | Docker **CPU** PyTorch image **[REPO]** | Continue for demo |
| Resolution | Capture target 1280×720; infer 640 default | Benchmark |
| FPS / cameras / latency | **Requires benchmarking** | AI-10 |
| GPU / VRAM / RAM | **Requires benchmarking** | Document measured |
| Evidence storage | Local `uploads/evidence/` | Size ∝ clip rate × cameras — ops estimate later |

**Defensible statements only:**

- **Development baseline:** CPU container can run single-stream demo; multi-cam real-time **not guaranteed** without measurement.  
- **Minimum practical deployment:** TBD after AI-10 (likely GPU for multi-cam custom YOLO).  
- **Recommended deployment:** TBD after benchmarks on institutional hardware.

---

## 23. Deployment Architecture

### Current [REPO]

Inference runs **inside the FastAPI process** (`LiveStreamManager` threads/loops), tightly coupled to MJPEG and DB persist.

### Options for later scale [ENGINEERING]

| Pattern | Pros | Cons |
|---------|------|------|
| **In-process (current)** | Simple; already works | AI crash risks API; harder horizontal scale |
| Separate AI worker/service | Isolate failures; scale infer | More ops; need IPC/queue |
| Per-camera worker processes | Parallelism | Orchestration complexity |

**C19 recommendation:** Keep **in-process** through AI-1–AI-5 while hardening fail-safes; **re-evaluate split AI service** at AI-10/AI-11 if multi-cam load or crash isolation demands it. Do not rewrite for microservices in early AI phases without measured need.

```text
Camera → AI inference (API process today) → event persist → evidence → alerts → portal
```

---

## 24. Model Versioning

Each deployed artifact should carry:

- model name / family (e.g. yolov8s-ufm)  
- model version  
- dataset version  
- training code / git commit  
- weights checksum  
- training date  
- evaluation summary  
- supported classes  
- config (imgsz, thresholds file version)

**Confirmed AI events should store model version** so audits can answer “which detector produced this?”

---

## 25. Failure & Recovery

| Failure | Safe behavior |
|---------|----------------|
| Camera disconnect / freeze | Session error; retry; no fake events |
| Decode failure | Skip frame |
| Model missing / load fail | Detect **off**; portal shows unavailable; manual UFM OK |
| Inference crash | Contain; restart session; do not write guilty cases |
| GPU unavailable | CPU fallback or disable with status |
| Evidence capture fail | Keep detection + flag; allow manual upload |
| WebSocket fail | Polling fallback **[REPO]** |
| AI restart | No retrospective auto-punishment |

Temporary AI failure must **not** silently create false UFM decisions.

---

## 26. Privacy / Security Considerations

### Technical controls [REPO + plan]

- Local inference; evidence on institutional storage paths.  
- RBAC on monitoring, detections, evidence, cases.  
- Audit logs for case/evidence actions.  
- No cloud vision APIs in architecture.

### Policy decisions (university must define — not invented here)

- Retention period for CCTV clips/evidence.  
- Consent for training recordings.  
- Who may export raw video.  
- Cross-border storage rules.

---

## 27. AI Scope Boundaries

| # | Decision |
|---|----------|
| 1 | AI = assistance/evidence — not autonomous discipline |
| 2 | Custom YOLO training/integration **deferred** to AI implementation phases |
| 3 | Learned posture classifier **deferred** |
| 4 | Paper-exchange / peer-interaction **deferred** |
| 5 | **Seat-map visualization EXCLUDED** despite Scope mention |
| 6 | SIS integration excluded |
| 7 | Campus SSO excluded |
| 8 | WebRTC mesh excluded |
| 9 | PKI / cryptographic signatures excluded |
| 10 | PDF report engine excluded |
| 11 | Official AU paper UFM form excluded |

Do not reintroduce excluded features in AI phases.

---

## 28. AI Implementation Roadmap

Adjusted for existing live baseline (evidence/alerts already partially present).

| Phase | Goal | Depends | Likely touchpoints | Model/data | Backend | Frontend | Tests | Acceptance | Rollback |
|-------|------|---------|-------------------|------------|---------|----------|-------|------------|----------|
| **AI-1** Baseline audit & integration | Honest status; wire env thresholds/cooldown; fail-safe missing weights | C19 | `live_stream.py`, `detection_policy.py`, live status API | None | Status fields; env wiring | Status banner only if needed | Policy unit + live status | Detect disables cleanly when no weights; thresholds env-driven | Revert env wiring |
| **AI-2** Custom exam-hall YOLO dataset + training | Annotated data + `best.pt` candidate | AI-1 | `ai/dataset/*`, `train_yolo.py` | Collect/annotate/train | None required for portal | None | Offline val scripts | Val metrics reported; artifact versioned | Keep COCO default |
| **AI-3** YOLO inference + object/event pipeline | Optional custom weights behind flag | AI-2 | `ufm_classes`, `live_stream` | Evaluate custom vs COCO | Flag + version on Detection | Show model mode | A/B on sample video | Custom only if improves held-out; else stay COCO | `YOLO_USE_CUSTOM=0` |
| **AI-4** Multi-frame + association | Stronger validation; tracker eval | AI-1/3 | `detection_policy`, tracker spike | Labeled persistence clips | Tracker optional | Minimal | Event-level FP tests | Fewer one-frame confirms vs baseline | Disable tracker |
| **AI-5** Evidence + alerts polish | Metadata completeness; semantics in payloads | AI-1 | `evidence_auto`, WS payloads | — | Enrich metadata | Clear “AI event ≠ verdict” copy | Evidence success tests | Package fields complete; RBAC unchanged | Revert payload fields |
| **AI-6** MediaPipe feature pipeline | Stable landmarks→features; optional hands research | AI-1 | `posture_analysis` | Feature dumps | Dependency story for MP | Optional overlays | Feature unit tests | Features logged with quality | Fallback OpenCV |
| **AI-7** Learned posture classifier | Correct/Incorrect gated | AI-6 | new weights path | Human labels | Feature flag | Do not claim until flagged | Compare vs rules | Beats rules on test **or** not enabled | Flag off |
| **AI-8** Paper exchange / peer interaction | Temporal candidate events | AI-4, AI-6 | new module | Temporal dataset | REVIEW-first events | Event type display | Event P/R | No auto-case; FP documented | Module off |
| **AI-9** Full eval + FP reduction | Thresholds from data | AI-3+ | configs | Test set freeze | Threshold files | — | Metric reports | Written acceptance criteria met | Prior threshold file |
| **AI-10** Performance / load | Hardware numbers filled | AI-3 | benchmarks | — | Profiling | — | Load scripts | Documented FPS/cam limits | Cap cameras |
| **AI-11** Production hardening | Versioning, recovery, ops | AI-9/10 | deploy docs, status | Checksums | Safe failure | Operator UI cues | Chaos/failure tests | Failures don’t touch case verdicts | Disable AI detect |

**C20 recommendation:** start **AI-1** only.

---

## 29. Open Engineering Decisions

1. Final YOLO variant (n/s/m/…) after benchmark.  
2. Tracker algorithm (if any) after MOT eval on hall footage.  
3. Posture classifier family after feature/dataset study.  
4. Paper-exchange model family after temporal data exists.  
5. Whether/when to split AI into a separate service.  
6. Clip container format long-term (WebP vs H.264 MP4) for institutional players.  
7. Exact dataset volume targets after pilot.  
8. Whether `person` is an explicit trained class vs detector default.  
9. Wiring `YOLO_DEVICE` into Ultralytics `predict(device=...)`.  
10. Institutional retention/consent policy (non-code).

---

## 30. Final C19 Readiness Checklist

| # | Check | Status |
|---|-------|--------|
| 1 | AI requirements traced to Scope or marked engineering | **Yes** |
| 2 | No excluded features reintroduced (seat-map, SIS, SSO, WebRTC, PKI, PDF, AU paper form) | **Yes** |
| 3 | No invented exact NN architectures where Scope silent | **Yes** |
| 4 | YOLO family clearly scope-required for OD | **Yes** |
| 5 | Custom exam-hall training distinguished from COCO baseline | **Yes** |
| 6 | Behavior/posture and paper exchange separate from OD | **Yes** |
| 7 | Data, annotation, split, leakage, eval, versioning documented | **Yes** |
| 8 | AI events do not bypass human UFM review | **Yes** |
| 9 | Existing RBAC + UFM workflow authoritative | **Yes** |
| 10 | C19 contains **no** implementation/code changes | **Yes** (docs only) |
| 11 | Lightweight doc/repo verification | Scope PDF previously extracted; traceability/SCOPE_COVERAGE/requirements/Docker/AI modules inspected |
| 12 | AI implementation **not** claimed complete | **Explicit** |

---

## Appendix — Key paths

| Path | Role |
|------|------|
| `VigilantEye Scope Document.pdf` | Authoritative AI requirements |
| `VigilantEye_Master_Cursor_Development_Learning_Protocol.md` | Dev protocol / YOLO guidance |
| `docs/REQUIREMENTS_TRACEABILITY.md` | R01–R20 status |
| `docs/SCOPE_COVERAGE.md` | Honest coverage map |
| `backend/live_stream.py` | Live OD + persist |
| `ai/detection_policy.py` | Decision + temporal helpers |
| `ai/ufm_classes.py` | Classes + weight resolution |
| `ai/posture_analysis.py` / `suspicion_score.py` | Behavior baseline |
| `backend/evidence_auto.py` | Evidence package |
| `backend/routers/ws_alerts.py` | Alerts |
