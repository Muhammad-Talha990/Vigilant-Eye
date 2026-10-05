# VigilantEye — Requirements Traceability Matrix
# Source: VigilantEye Scope Document.pdf (13 pages) + user submission prompt
# Updated: 2026-10-01 — C11-B role access + navigation cleanup; seat-map project exclusion recorded.

| ID | Scope | Requirement | Status | Evidence | Remaining / acceptance |
|----|-------|-------------|--------|----------|------------------------|
| R01 | p6 §5.1 | Live CCTV/IP + webcam monitoring | **Verified partial** | `live_stream.py` RTSP/file/webcam; MJPEG UI | Multi-hall fleet ops; WebRTC mesh FUTURE |
| R02 | p7 §6.1 | YOLOv8 object detection (phone, watch, gadgets, notes, paper exchange, head) | **Partial** | COCO + policy; custom `best.pt` often absent | Custom train for chits/exchange; paper exchange temporal **deferred to final AI phase** |
| R03 | p7 | Multi-frame confirmation before alert | **Verified** | `SessionTracker` | Calibrate on hall footage |
| R04 | p7 | Real-time Invigilator/HOD alerts | **Partial→improved** | Portal poll + **WebSocket `/ws/alerts`** | Verify under load |
| R05 | p8 §6.2 | Auto snapshot/clip evidence + metadata | **Verified** | `evidence_auto.py`, detection_id link | Pre/post buffer tunable; integrity hash **partial** |
| R06 | p8 §6.3 | Case create + sign-off | **Verified (C11-B)** | Create = Invigilator only; reviews + typed sign-off; `camera_id` on case (C5) | Not PKI; HOD no longer creates cases |
| R07 | p8 §6.4 | Six role dashboards | **Verified (C11-B)** | `navByRole.js` + `roleAccess.js` + route gates | Seat-map viz **excluded by project decision** (PDF still REQUIRED — see FROZEN §12) |
| R08 | p9 §6.5 | Portal + email notifications | **Verified** | HOD+Exam+UFM+student on create (C4); `EMAIL_MOCK` / optional SMTP | Institutional SMTP credentials for live mail |
| R09 | p9 §6.6 | Audit trail | **Verified** | `audit_logs` + CSV export lite (C9); admin vs operational audit split (C11-B) | Not absolute tamper-proof vs DBA |
| R10 | p9–10 | Result hold / transcript block | **Verified local** | Auto hold on APPROVE; list/release UI (C8: no manual create UI required) | SIS integration **OUT OF SCOPE** |
| R11 | p10 Tools | React+Tailwind, FastAPI, Postgres, OpenCV, YOLOv8 | **Verified** | Stack matches | — |
| R12 | p10 | MediaPipe pose/gaze | **Partial** | `ai/posture_analysis.py` + live overlay; OpenCV fallback when MediaPipe unavailable | Install MediaPipe on supported Python or provide wheel |
| R13 | p10 | Suspicion score / angle classifier | **Partial** | Rule-based `suspicion_score.py` in live loop | Learned regressor **deferred to final AI phase** |
| R14 | p10 | WebSockets | **Implemented** | `ws_hub.py`, `routers/ws_alerts.py`, AppLayout client | — |
| R15 | p10 | Docker | **Implemented scaffold** | `Dockerfile` + `docker-compose.yml` | Needs image build verification on target host |
| R16 | Prompt | Ordinary watch not → phone | **Verified policy** | remote/watch unmapped; tests | COCO still may misread watch as phone visually |
| R17 | Prompt | Paper page not → electronic_gadget | **Mitigated** | Unknown≠gadget; book→notes REVIEW-only; large-box phone→notes heuristic | Custom paper model still required |
| R18 | Prompt | Paper chits / exchange | **Missing / deferred AI** | notes_paper class only | Dataset + temporal exchange module (final AI phase) |
| R19 | Prompt | Seat map ↔ roster | **Missing / excluded UI** | seat_location string only | **Seat-map UI not implemented** (project decision C11-B; PDF conflict documented); SIS seating FUTURE |
| R20 | Prompt | Candidate track IDs | **Partial** | Spatial bins + face track ids | No stable multi-object tracker / identity |

## Blockers
1. **MediaPipe on Python 3.13**: often no clean wheel → OpenCV Haar geometry fallback (`estimator=opencv_fallback`).
2. **Custom YOLO `best.pt`**: not present / weak → COCO default. Training needs GPU time + annotated chit/watch data.
3. **SMTP / SIS**: no institutional credentials → email mock; local result holds only.
4. **Paper exchange & learned posture classifier**: deferred to **final AI phase** (intentional).
5. **Live Postgres on this host (C10)**: `alembic current` failed (password auth to localhost:5432). Script head verified as `20260930_0005_case_camera`.

## How to validate
- `cd backend && pytest -q` (C10: **235 passed**)
- `cd frontend && npm run build` + `node --test src/config/reportStats.test.mjs`
- Live Monitoring: detect on + posture overlays; WebSocket banner on confirm
- Create case from detection with evidence preview + camera metadata
- Full role workflow per `docs/DEMO_RUNBOOK.md`
- Reports: department/semester tables; case CSV; Audit Trail CSV
