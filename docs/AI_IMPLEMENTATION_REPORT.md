# AI Implementation Report — VigilantEye (AI-1 phase)

**Date:** 2026-10-04  
**Final status (this phase):** see `AI_CORE_IMPLEMENTATION_REPORT.md` → **C — PARTIALLY IMPLEMENTED**

---

## Baseline audit (summary)

| Area | Classification |
|------|----------------|
| YOLOv8n Ultralytics live path | A — implemented |
| COCO weights default | B — baseline/demo for exam classes; **current live default** |
| Custom `best.pt` | C/E/F — exists; **measured mAP ≈ 0** on matched weak val → not production |
| Detection policy IGNORE/REVIEW/CONFIRM | A |
| Multi-frame SessionTracker | A (cooldown never-emitted fix this phase) |
| Evidence auto SNAPSHOT/CLIP | A |
| WS alerts | A |
| Monitoring UI Invigilator-only | A |
| Alert recipients | A — Invigilator (`MONITOR_ROLES`) |
| model_version on detections | A |
| Paper exchange model | D/E — deferred |
| Learned posture classifier | D/E — deferred |
| ByteTrack etc. | G — not required; spatial bins used |
| Session-aware split | A tooling / not applied |
| Dataset licenses | F — NOT VERIFIED in-repo |

---

## Changes in this phase

1. `detection_bridge.notify_detection_alert` → `MONITOR_ROLES` (Invigilator).  
2. `detections.model_version` + Alembic revision.  
3. Live status exposes model version, device, inference latency/FPS.  
4. Monitoring UI AI status panel + confirmed/review event feed wording.  
5. `evaluate_model.py` taxonomy mismatch guard + measured eval artifact.  
6. `benchmark_inference.py`, `dataset_quality_pipeline.py`, `session_aware_split.py`.  
7. SessionTracker cooldown fix (missing last-emit ≠ time 0).  
8. AI documentation set under `docs/AI_*.md` + `AI_CORE_IMPLEMENTATION_REPORT.md`.  
9. Tests: `test_detection_alert_recipients.py`, expanded SessionTracker tests.

---

## Event ladder (preserved)

RAW → SUSPICIOUS OBSERVATION → multi-frame → CONFIRMED AI EVENT → evidence → human review → optional UFM (Invigilator creates case).

AI never auto-approves / guilt-decides.
