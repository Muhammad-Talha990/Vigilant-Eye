# Scope coverage — Master Protocol §5 mapping

Honest map of VigilantEye FYP submission features vs campus-enterprise FUTURE items.
Master protocol: `VigilantEye_Master_Cursor_Development_Learning_Protocol.md`.

| Protocol item | Status | Notes |
|---------------|--------|-------|
| Live exam monitoring (camera stream + AI overlay) | **Implemented** | MJPEG live sessions; webcam / file / RTSP URL |
| Confirmed detection → portal | **Implemented** | Persist streak + cooldown → `detections` |
| Auto evidence (snapshot / short clip) | **Implemented** | JPEG (+ optional MP4) under `uploads/evidence/`; `detection_id` linked |
| Draft / create UFM case from detection | **Implemented** | `POST /detections/{id}/create-draft-case` + UI; attaches orphan evidence |
| Case enrichment (student / exam / room) | **Implemented** | Enriched list/detail APIs + Cases UI |
| Digital sign-off (create + reviews) | **Implemented** | Typed name + ack checkbox; `CASE_SIGNED` / review audit (not PKI) |
| Workflow HOD → DEC → Exam → UFM | **Implemented** | `PENDING` / `UNDER_REVIEW` → … → APPROVED/REJECTED |
| Student clarification | **Implemented** | Linked `students.user_id` + DEMO001 seed |
| Portal notifications | **Implemented** | Role queues + student + reporter on status changes |
| Email notify | **Implemented (optional)** | `SMTP_*` sends; else `EMAIL_MOCK` console/audit-safe log |
| Result hold on APPROVE | **Implemented** | Auto `ResultControl` HELD / BLOCKED; list + release UI on Result Holds. Separate *manual create-hold* screen **not required** (Phase C8 reassessment; SCOPE-023 already COMPLETE). |
| Audit trail | **Implemented** | Create, sign, review, evidence, hold events; Audit Trail UI + **CSV export lite** (C9 / SCOPE-025) |
| Reports / export | **Implemented** | Live KPIs + **CSV** cases export (not PDF) |
| Master data / staff users | **Implemented** | Rooms, cameras, exams, students; **staff provisioning = Administrator only (C11-B)**; **Invigilator has no Students / Exam Setup / Reports UI** |
| Help / FAQ | **Implemented** | Sign-off, live evidence, clarifications |
| Professional portal UI/UX | **Implemented (C11-C)** | Design system polish, role dashboards, responsive tables/cards; no business-logic change |
| Campus SSO / IdP | **FUTURE** | JWT email/password only |
| WebRTC multi-cam mesh | **FUTURE** | Current release uses MJPEG live sessions |
| PKI / cryptographic e-sign | **FUTURE** | Name+ack acknowledgment only |
| Full SIS / ERP grade sync | **FUTURE** | Manual student records + result hold table |
| WebSockets push notifications | **Implemented** | `/ws/alerts` + AppLayout client (also keeps 5s poll) |
| MediaPipe behavior models | **Partial** | `ai/posture_analysis.py` + live overlays; OpenCV fallback if MediaPipe unavailable (Py3.13 blocker) |
| Suspicion score engine | **Partial** | Rule-based `ai/suspicion_score.py` (provisional thresholds); learned classifier incomplete |
| Docker | **Implemented** | Dev: `docker-compose.yml` + `start-dev.ps1` (Postgres + API + Vite). Prod scaffold: `docker-compose.prod.yml` + nginx frontend (no TLS terminator in-repo) |
| Paper ≠ electronic_gadget | **Mitigated** | Mapping + COCO book REVIEW-only + large-box heuristic; custom chit model still needed |
| Traceability matrix | **Docs** | `docs/REQUIREMENTS_TRACEABILITY.md` |
| Dataset register | **Docs** | `docs/DATASET_REGISTER.md` |

## Verification shortcuts

1. `python seed_all_demo.py` then backend + frontend  
2. Invigilator: Live demo clip → detection → draft case → sign-off create  
3. Student: case + notification → clarification  
4. HOD→DEC→Exam→UFM signed reviews → result hold → audit  
5. Evidence **Open file**; Reports **Export cases CSV**  
6. `npm run build` + `pytest -q` (from `backend/`)
