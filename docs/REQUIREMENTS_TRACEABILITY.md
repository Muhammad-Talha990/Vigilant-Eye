# VigilantEye — Requirements Traceability Matrix
# Source: VigilantEye Scope Document.pdf (13 pages) + user submission prompt
# Updated: 2026-09-14 — living document; statuses are evidence-based.

| ID | Scope | Requirement | Status | Evidence | Remaining / acceptance |
|----|-------|-------------|--------|----------|------------------------|
| R01 | p6 §5.1 | Live CCTV/IP + webcam monitoring | **Verified partial** | `live_stream.py` RTSP/file/webcam; MJPEG UI | Multi-hall fleet ops; WebRTC mesh FUTURE |
| R02 | p7 §6.1 | YOLOv8 object detection (phone, watch, gadgets, notes, paper exchange, head) | **Partial** | COCO + policy; custom `best.pt` often absent | Custom train for chits/exchange; paper exchange temporal **missing** |
| R03 | p7 | Multi-frame confirmation before alert | **Verified** | `SessionTracker` | Calibrate on hall footage |
| R04 | p7 | Real-time Invigilator/HOD alerts | **Partial→improved** | Portal poll + **WebSocket `/ws/alerts`** | Verify under load |
| R05 | p8 §6.2 | Auto snapshot/clip evidence + metadata | **Verified** | `evidence_auto.py`, detection_id link | Pre/post buffer tunable; integrity hash **partial** |
| R06 | p8 §6.3 | Case create + sign-off Invigilator/HOD | **Verified** | CreateCase + reviews + typed sign-off | Not PKI |
| R07 | p8 §6.4 | Six role dashboards | **Verified** | `navByRole.js` + pages | Seat-map viz **minimal/missing** |
| R08 | p9 §6.5 | Portal + email notifications | **Verified optional email** | `notify_helpers`, `EMAIL_MOCK` | SMTP credentials = blocker for real email |
| R09 | p9 §6.6 | Audit trail | **Verified** | `audit_logs` | Not absolute tamper-proof vs DBA |
| R10 | p9–10 | Result hold / transcript block | **Verified local** | `ResultControl` on APPROVE | SIS integration **blocked** (no institutional API) |
| R11 | p10 Tools | React+Tailwind, FastAPI, Postgres, OpenCV, YOLOv8 | **Verified** | Stack matches | — |
| R12 | p10 | MediaPipe pose/gaze | **Partial** | `ai/posture_analysis.py` + live overlay; **MediaPipe wheel blocked on Py3.13 / pip lock** → OpenCV fallback | Install MediaPipe on supported Python or provide wheel |
| R13 | p10 | Suspicion score / angle classifier | **Partial** | Rule-based `suspicion_score.py` in live loop | Learned regressor **incomplete** (no labeled angle dataset trained) |
| R14 | p10 | WebSockets | **Implemented** | `ws_hub.py`, `routers/ws_alerts.py`, AppLayout client | — |
| R15 | p10 | Docker | **Implemented scaffold** | `Dockerfile` + `docker-compose.yml` | Needs image build verification on target host |
| R16 | Prompt | Ordinary watch not → phone | **Verified policy** | remote/watch unmapped; tests | COCO still may misread watch as phone visually |
| R17 | Prompt | Paper page not → electronic_gadget | **Mitigated** | Unknown≠gadget; book→notes REVIEW-only; large-box phone→notes heuristic | Custom paper model still required |
| R18 | Prompt | Paper chits / exchange | **Missing / partial** | notes_paper class only | Dataset + temporal exchange module |
| R19 | Prompt | Seat map ↔ roster | **Missing** | seat_location string only | Implement regions + roster link |
| R20 | Prompt | Candidate track IDs | **Partial** | Spatial bins + face track ids | No stable multi-object tracker / identity |

## Blockers
1. **MediaPipe on Python 3.13**: pip install failed (no clean wheel / cv2 file lock while uvicorn running). Fallback: OpenCV Haar geometry (`estimator=opencv_fallback`).
2. **Custom YOLO `best.pt`**: not present / weak → COCO default. Training needs GPU time + annotated chit/watch data.
3. **SMTP / SIS**: no institutional credentials → email mock; local result holds only.
4. **Paper exchange & learned posture classifier**: no adequate labeled temporal dataset downloaded in this session.

## How to validate
- `cd backend && pytest -q`
- Live Monitoring: detect on + posture overlays; WebSocket banner on confirm
- Create case from detection with evidence preview
- Full role workflow per `docs/DEMO_RUNBOOK.md`
