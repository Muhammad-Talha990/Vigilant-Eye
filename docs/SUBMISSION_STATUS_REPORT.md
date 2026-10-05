# VigilantEye — Final submission status report (2026-09-14)

This is an evidence-based status after scope PDF review + repo audit + implementation pass.
It does **not** claim 100% scope completion.

## 1. Requirements verified complete (with evidence)
- Auth + six role dashboards / nav (`frontend` + JWT FastAPI).
- Live monitoring MJPEG: webcam / file / RTSP (`backend/live_stream.py`).
- YOLO object pipeline + temporal confirmation (`detection_policy.SessionTracker`).
- Auto evidence snapshot/clip, case draft/create, digital name+ack sign-off.
- Workflow Invigilator → HOD → DEC → Exam → UFM; student clarification.
- Portal notifications; optional SMTP (`EMAIL_MOCK` without credentials).
- Local result hold / transcript block table; audit logs; CSV export.
- Ordinary-watch policy (no generic watch→smart_watch); remote excluded.
- Unit tests: detection policy + suspicion score (12 passed this session).

## 2. Newly implemented / fixed this pass
- Paper→gadget mitigations: unknown never maps to gadget; COCO `book` → `notes_paper` **REVIEW-only**; large desk-area “phone” boxes reclassified to notes for review.
- `ai/posture_analysis.py` head orientation (MediaPipe if available, else OpenCV fallback).
- `ai/suspicion_score.py` time-based provisional score engine + live overlays/events.
- WebSocket `/ws/alerts` + frontend live alert banner (`AppLayout`).
- Docker scaffold (`Dockerfile`, `docker-compose.yml`).
- Docs: `REQUIREMENTS_TRACEABILITY.md`, `DATASET_REGISTER.md`, posture model honesty README.
- Detections/Notifications already poll live; badges + WS refresh.

## 3. Changed files (high level)
- `ai/detection_policy.py`, `ai/posture_analysis.py`, `ai/suspicion_score.py`, `ai/posture_model_README.md`
- `backend/live_stream.py`, `backend/ws_hub.py`, `backend/routers/ws_alerts.py`, `backend/main.py`
- `backend/tests/test_detection_policy.py`, `backend/tests/test_suspicion_score.py`
- `frontend/src/components/AppLayout.jsx` (+ prior detections/notifications live poll)
- `docs/REQUIREMENTS_TRACEABILITY.md`, `DATASET_REGISTER.md`, `SCOPE_COVERAGE.md`
- `Dockerfile`, `docker-compose.yml`

## 4. Datasets actually downloaded
- **None new** this session. Runtime uses Ultralytics COCO weights already in `ai/weights/yolov8n.pt`.
- Register + collection plan: `docs/DATASET_REGISTER.md`.

## 5. Models actually trained
- **No new training run** this session.
- Weights used: **COCO `yolov8n.pt`** by default; custom `best.pt` only if `YOLO_USE_CUSTOM=1` and file exists.
- Learned posture classifier: **not trained** (documented incomplete).

## 6. Measured accuracy / latency / hardware
- Not re-benchmarked on hall footage this session.
- Policy unit tests only (no mAP claim).
- Hardware: developer Windows + Python 3.13 venv (see local machine).

## 7. Tests / workflows verified
- `pytest` policy + suspicion: **12 passed**.
- Full six-role browser E2E: follow `docs/DEMO_RUNBOOK.md` (manual; restart backend to load WS + posture).

## 8. Startup / demo
```text
# DB migrate/seed as usual
cd backend
.\venv\Scripts\Activate.ps1
uvicorn main:app --reload --host 127.0.0.1 --port 8000

cd frontend
npm run dev
```
Demo: Invigilator Live Monitoring (sample clip, Detect+Persist) → WebSocket banner / Detections live list → Create case + evidence preview → role chain → student clarification → result hold → audit.

Optional Docker: `docker compose up --build` (API+Postgres; set secrets).

## 9. Remaining blockers
| Blocker | Need |
|---------|------|
| MediaPipe wheel on Python 3.13 / file lock during pip | Python 3.11 env or stop uvicorn then `pip install mediapipe` |
| Custom YOLO for chits / normal_watch / paper exchange | Annotated dataset + GPU train → `best.pt` |
| Learned posture classifier | Independent human-labeled angle sequences |
| Seat map ↔ roster | Product design + schema/UI |
| Real email / SIS transcript | Institutional SMTP + SIS API credentials |
| Paper exchange temporal module | Tracking + interaction model + labels |

**Do not claim:** high accuracy, complete MediaPipe gaze, SIS-enforced transcript blocks, or trained posture classifier without the above.
