# FROZEN SCOPE BASELINE — Phase A

**Freeze date:** 2026-09-30  
**Phase:** A — Scope freeze only (no feature implementation)  
**Status:** FROZEN pending stakeholder review of classifications

---

## 1. Authoritative document

| Rank | Document | Location | Role |
|------|----------|----------|------|
| **1 — AUTHORITATIVE** | VigilantEye Scope Document.pdf (Project Proposal, 13 pages) | `Vigilant Eye/VigilantEye Scope Document.pdf` | Final FYP scope authority |
| 2 — Secondary summary | `VigilantEye_Master_Cursor_Development_Learning_Protocol.md` §5–§8 | Repo root | Implementation guide; yields to PDF on conflict |
| 3 — Living evidence map | `docs/REQUIREMENTS_TRACEABILITY.md` | Docs | Traceability + status; not authority |
| 4 — Honesty / FUTURE map | `docs/SCOPE_COVERAGE.md` | Docs | Separates implemented vs FUTURE; not authority |

### PDF identity (workspace copy)

- **Path:** `C:\Users\KING\Desktop\NEW PROJ\Vigilant Eye\VigilantEye Scope Document.pdf`
- **Pages:** 13  
- **Title:** Project Proposal — VigilantEye  
- **Authors:** Muhammad Abdullah (232514), Muhammad Talha (232950), Muzamil Wasif (232430)  
- **Supervisor:** Dr. Muhammad Bilal Khan  
- **File date (workspace):** 2026-09-24 (680,449 bytes)  

Other copies found (not used as freeze authority unless identical):

- `Downloads\VigilantEye_Scope_Document UPDATED.pdf` (2026-06-09, smaller — older draft)
- `Downloads\VigilantEye Scope Document.pdf` (2026-07-04)
- `Desktop\FYP FINAL\VigilantEye Scope Document (1).pdf` (same size as workspace)

**Freeze uses the workspace 13-page Project Proposal PDF only.**

---

## 2. Authority conflicts (resolved)

| Topic | PDF | Master Protocol / secondary | Resolution for freeze |
|-------|-----|----------------------------|------------------------|
| Roles in §5.1 auth bullet | Invigilators, Examination Department, UFM Committee, Students | Six roles incl. HOD, DEC | **HOD + DEC REQUIRED** via PDF §4.1 / §6.4 (not only §5.1 bullet) |
| Digital signatures | “digital signature” Invigilator + HOD (§6.3) | PKI marked FUTURE in SCOPE_COVERAGE | **Digital sign-off REQUIRED**; **PKI OUT OF SCOPE** |
| Seat location | “seat location (if mapped)” (§6.2) | Seat map ↔ roster as missing (R19 Prompt) | **Conditional/Optional** for evidence; see SCOPE-028 |
| Seat map visualization | Assigned in §10 work division; “spatial seat mapping” in §2 solution column | R19 Prompt | **REQUIRED as declared team deliverable (§10)**; institutional seating DB integration **FUTURE** without SIS |
| Paper exchange | Explicit in §6.1 | R18 Prompt + Master §5 | **REQUIRED** (PDF wins) |
| Learned posture DL | Explicit in §8 tools table | Incomplete in SCOPE_COVERAGE | **REQUIRED** (PDF tools) |
| WebRTC mesh | Not mentioned (RTSP + WebSocket are) | FUTURE in SCOPE_COVERAGE | **OUT OF SCOPE** |
| Campus SSO | Not mentioned | FUTURE | **OUT OF SCOPE** |
| SIS / ERP sync | Not mentioned as product requirement; §7 institutional DB for seating/enrollment | FUTURE | **OUT OF SCOPE** for SIS sync; local holds **REQUIRED** |
| Official AU paper UFM form layout | Not mentioned; digital form fields listed | Implementation / CreateCase AU styling | **OUT OF SCOPE** as official paper-form parity; digital form **REQUIRED** |
| ADMINISTRATOR role | Not in PDF stakeholder dashboards | Implemented for Google provisioning | **OUT OF SCOPE** (implementation decision); must stay non-operational |
| R16–R20 “Prompt” rows | Only some collide with PDF | Traceability secondary | Prompt-only rows that are **not** in PDF = **not authoritative** |

---

## 3. Contested items — REQUIRED for current FYP?

| Audit ID | Topic | PDF support | Freeze class | Remediation required? |
|----------|-------|-------------|--------------|----------------------|
| SCOPE-027 | Paper exchange detection | §6.1 lists “paper exchange” as detected UFM activity | **REQUIRED** | **YES** (currently GAP) |
| SCOPE-028 | Seat map ↔ roster | Evidence: §6.2 “if mapped”; Viz: §10 “Seat map visualization”; Data: §7 seating plans | **SPLIT:** seat_location metadata = **OPTIONAL/CONDITIONAL**; seat-map UI = **REQUIRED**; institutional seating SIS = **FUTURE** | **YES** for seat-map UI (missing); **NO** for full SIS seating |
| SCOPE-022 | Learned posture classifier (Correct/Incorrect from MediaPipe angles) | §8 “Python / Deep Learning Models … Correct or Incorrect” | **REQUIRED** | **YES** (rule-based only today) |
| SCOPE-030 | Case camera ID | §5.1 case fields include “camera ID” | **REQUIRED** | **DONE (C5)** — `ufm_cases.camera_id` nullable FK |
| SCOPE-035 | Official AU UFM paper form | **Not in PDF** | **OUT OF SCOPE** | **NO** for AU paper parity; digital form fields still required separately |
| SCOPE-036 | PDF / rich reporting | Exam stats §5.1 / §6.4; audit reports §6.6; **no PDF export stated** | **REQUIRED:** dashboard stats + audit reports; **OUT OF SCOPE:** PDF export engine | Stats/dept/semester + case/audit CSV: **DONE (C6–C9)**; PDF engine: **NO** |
| — | PKI / cryptographic e-sign | Not in PDF | **OUT OF SCOPE / FUTURE** | **NO** (typed digital sign-off satisfies “digital signature” for FYP unless supervisor demands PKI) |
| — | SIS integration | Not a product requirement | **OUT OF SCOPE / FUTURE** | **NO** for SIS; local result hold/transcript block **still REQUIRED** |
| — | Campus camera fleet | §5 CCTV/IP; §8 RTSP; scalable halls | **REQUIRED:** live CCTV/IP/RTSP capability; **NOT REQUIRED:** verified multi-building AU fleet rollout | Capability exists (PARTIAL ops); fleet proof = demo/ops, not new scope item |

---

## 4. Frozen requirement list (SCOPE-001 onward)

**Legend — Classification:** REQUIRED | OPTIONAL | CONDITIONAL | FUTURE | OUT OF SCOPE  
**Legend — Status:** COMPLETE | PARTIAL | GAP | N/A  
**Remediation:** YES / NO / DEFER

| ID | Exact requirement (from PDF wording, condensed without changing meaning) | Source | Section/page | Class | Status | Evidence | Remediation |
|----|--------------------------------------------------------------------------|--------|--------------|-------|--------|----------|-------------|
| SCOPE-001 | Live CCTV/IP camera feeds monitored in real time in control rooms / HOD offices | PDF | §5, §5.1 p6 | REQUIRED | PARTIAL | RTSP/file/webcam MJPEG | DEFER fleet-scale; keep capability |
| SCOPE-002 | YOLO-based object detection of phones, smart watches, electronic gadgets, hidden notes, paper exchange, suspicious hand/head movements | PDF | §6.1 p7 | REQUIRED | PARTIAL | COCO + policy; exchange GAP | YES (esp. exchange, custom classes) |
| SCOPE-003 | Behavior analysis algorithms alongside YOLO | PDF | §6.1 p7 | REQUIRED | PARTIAL | posture + suspicion rules | YES toward MediaPipe+DL |
| SCOPE-004 | Repeated-frame / multi-frame validation before final alert | PDF | §5.1 p6; §6.1.2 p7 | REQUIRED | COMPLETE | SessionTracker | NO |
| SCOPE-005 | Confidence score and timestamp per detection | PDF | §6.1.3 p7 | REQUIRED | COMPLETE | detections table | NO |
| SCOPE-006 | Real-time alerts on Invigilator and HOD monitoring dashboards | PDF | §6.1.1 p7; §6.5 p9 | REQUIRED | PARTIAL | portal + WS | DEFER load test |
| SCOPE-007 | Auto short video clip + snapshot evidence with metadata (camera ID, room, seat if mapped, timestamp, confidence) | PDF | §6.2 p8 | REQUIRED | PARTIAL | evidence_auto; seat often empty | YES if seat mapping added |
| SCOPE-008 | Manual evidence upload by invigilators | PDF | §6.2 p8; Intro | REQUIRED | COMPLETE | POST /evidence | NO |
| SCOPE-009 | Digital UFM case with student/exam details: ID, name, department, date, time, room, **camera ID** | PDF | §5.1 p6–7 | REQUIRED | COMPLETE | enrich + `ufm_cases.camera_id` (C5) | NO |
| SCOPE-010 | Digital UFM form: violation type, description, remarks, evidence attachment | PDF | §5.1 p7 | REQUIRED | COMPLETE | CreateCase + API | NO (AU paper layout OOS) |
| SCOPE-011 | Digital signature from Invigilator and HOD | PDF | §6.3 p8 | REQUIRED | PARTIAL | name+ack (not PKI) | NO unless PKI demanded |
| SCOPE-012 | Submit structured case into institutional workflow (Exam Dept / chain) | PDF | §6.3 p8; §6.4 | REQUIRED | COMPLETE | HOD→DEC→EXAM→UFM | NO |
| SCOPE-013 | Role-based auth + dashboards: Invigilator, HOD, DEC, Exam Dept, UFM Committee, Student | PDF | §5.1; §6.4 p8 | REQUIRED | COMPLETE | navByRole + APIs | NO |
| SCOPE-014 | Invigilator: create cases, upload evidence, remarks, submit, track status | PDF | §6.4 p8 | REQUIRED | COMPLETE | Cases UI | NO |
| SCOPE-015 | HOD: review, verify evidence, remarks, approve/return, forward to DEC | PDF | §6.4 p8 | REQUIRED | COMPLETE | FORWARD/RETURN | NO |
| SCOPE-016 | DEC: review, recommendations, preliminary investigation, forward to Exam Dept | PDF | §6.4 p8 | REQUIRED | PARTIAL | FORWARD + remarks (no separate investigation entity) | DEFER unless supervisor requires separate investigation records |
| SCOPE-017 | Exam Dept: all cases, stats, pending investigations, result hold/transcript restrictions, forward to UFM | PDF | §5.1; §6.4 p8 | REQUIRED | COMPLETE (lite) | holds + KPIs + dept/semester reports (C7) | NO |
| SCOPE-018 | UFM Committee: evidence review, student history, final decision, notifications | PDF | §6.4 p8 | REQUIRED | PARTIAL | APPROVE/REJECT; history limited | DEFER rich history |
| SCOPE-019 | Student: view case, progress, notifications, outcomes, submit remarks/clarifications | PDF | §6.4 p8 | REQUIRED | COMPLETE | clarification once (C3) | NO |
| SCOPE-020 | Portal + email notifications on case submission to Exam Dept and UFM Committee | PDF | §5.1 p7; §6.5 p9 | REQUIRED | COMPLETE | HOD+Exam+UFM+student on create (C4); SMTP optional | NO |
| SCOPE-021 | Continuous status updates (Pending, Under Review, Approved, Rejected, etc.) | PDF | §6.5 p9 | REQUIRED | COMPLETE | CASE_STATUS; no active HOD_VERIFICATION (C2) | NO |
| SCOPE-022 | Detection alerts to Invigilator/HOD dashboards | PDF | §6.5 p9 | REQUIRED | PARTIAL | WS + detections | DEFER |
| SCOPE-023 | Result hold, transcript blocking, controlled release after final decision | PDF | §5.1 p7 | REQUIRED | COMPLETE | ResultControl local | NO (SIS OOS) |
| SCOPE-024 | Audit trail of create, modify, evidence, assignments, reviews, decisions + user/role/time | PDF | §6.6 p9 | REQUIRED | COMPLETE (lite) | audit_logs + UI; not tamper-proof vs DBA | DEFER tamper-proof claims |
| SCOPE-025 | Structured audit reports for case histories / user actions | PDF | §6.6.4 p9 | REQUIRED | COMPLETE (lite) | Audit UI + CSV export (`/audit-logs/export.csv`); not rich/PDF pack | NO |
| SCOPE-026 | Stack: React+Tailwind, FastAPI, Postgres, OpenCV, YOLOv8, MediaPipe, WebSocket, RTSP, Docker | PDF | §8 p10 | REQUIRED | PARTIAL | MediaPipe fallback; Docker scaffold | YES MediaPipe env |
| SCOPE-027 | Custom DL classification/regression on MediaPipe angles → Correct/Incorrect posture | PDF | §8 p10 | REQUIRED | GAP | rule suspicion only | YES |
| SCOPE-028 | Paper exchange detection (as named UFM activity) | PDF | §6.1 p7 | REQUIRED | GAP | missing temporal module | YES |
| SCOPE-029 | Seat location on evidence when mapped | PDF | §6.2 p8 | CONDITIONAL | PARTIAL | column exists; rarely set | YES with mapping |
| SCOPE-030 | Seat map visualization | PDF | §10 p11 | REQUIRED (PDF) | **EXCLUDED by project decision (C11-B)** | missing UI — will not implement | Documented conflict; not a delivery gap for this build |
| SCOPE-031 | Integrate seating plans / enrollment / hall layouts via institutional databases | PDF | §7 p9–10 | FUTURE | GAP | enrollments local only | NO for FYP unless DB access granted |
| SCOPE-032 | Fine-tune YOLO on phones, watches, devices, paper cheating materials | PDF | §7 p9 | REQUIRED | PARTIAL | training scripts; COCO default | YES for demo quality |
| SCOPE-033 | Suspicion score matrix (work division) | PDF | §10 p11 | REQUIRED | PARTIAL | rule engine | Align with SCOPE-027 |
| SCOPE-034 | WebSocket instant alerts | PDF | §8 p10 | REQUIRED | COMPLETE | /ws/alerts | NO |
| SCOPE-035 | Official Air University paper UFM form layout / Deputy / UMCC sections | — | **Not in PDF** | OUT OF SCOPE | N/A | CreateCase AU styling is extra | NO |
| SCOPE-036 | PDF export engine for reports | — | **Not in PDF** | OUT OF SCOPE | N/A | CSV + KPIs exist | NO |
| SCOPE-037 | PKI / cryptographic e-signatures | — | **Not in PDF** | OUT OF SCOPE / FUTURE | N/A | SCOPE_COVERAGE FUTURE | NO |
| SCOPE-038 | Full SIS/ERP grade sync | — | **Not in PDF** | OUT OF SCOPE / FUTURE | N/A | local ResultControl | NO |
| SCOPE-039 | Campus SSO / IdP | — | **Not in PDF** | OUT OF SCOPE / FUTURE | N/A | Google OAuth impl decision | NO |
| SCOPE-040 | WebRTC multi-cam mesh | — | **Not in PDF** | OUT OF SCOPE / FUTURE | N/A | MJPEG+RTSP | NO |
| SCOPE-041 | ADMINISTRATOR operational UFM powers | — | **Not in PDF** | OUT OF SCOPE | N/A | Admin isolated (correct) | NO — keep isolated |
| SCOPE-042 | Ordinary-watch≠phone / paper≠gadget mitigations | Traceability “Prompt” R16–R17 | **Not explicit in PDF** | OPTIONAL (quality) | PARTIAL | detection_policy | OPTIONAL |
| SCOPE-043 | Stable multi-object candidate track IDs | Traceability “Prompt” R20; PDF “tracks across frames” soft | CONDITIONAL | PARTIAL | spatial bins | DEFER |

---

## 5. Requirements only in secondary docs (NOT PDF-supported)

These must **not** be treated as frozen REQUIRED scope unless supervisor amends the PDF:

| Item | Where it appears | Freeze |
|------|------------------|--------|
| WebRTC mesh | SCOPE_COVERAGE FUTURE; R01 remaining | OUT OF SCOPE |
| PKI e-sign (as distinct from digital signature) | SCOPE_COVERAGE FUTURE | OUT OF SCOPE |
| Full SIS/ERP sync | SCOPE_COVERAGE; R10 remaining | OUT OF SCOPE |
| Campus SSO | SCOPE_COVERAGE | OUT OF SCOPE |
| Official AU paper UFM form / UMCC/Deputy fields | Implementation UI copy; not PDF | OUT OF SCOPE |
| PDF report generator | Evaluator honesty notes | OUT OF SCOPE |
| R16–R17 watch/paper mitigations | Traceability “Prompt” | OPTIONAL quality |
| R19 “seat map ↔ roster” as single mandatory IDOR-style product | Prompt + matrix | Superseded by PDF split SCOPE-029/030/031 |
| ADMINISTRATOR as scope role | Master Protocol / phases | OUT OF SCOPE (keep as access tool) |

---

## 6. Master Protocol alignment

Master Protocol §5 is a faithful **summary** of the PDF for AI, evidence, cases, roles, workflow, notifications, result controls, and audit.  

**Differences to freeze:**

1. Protocol lists “seat location where available” — matches PDF “if mapped” (CONDITIONAL).  
2. Protocol does not elevate PKI, SIS, WebRTC — correct.  
3. Protocol does not list seat-map UI or learned posture DL explicitly in §5 bullets; **PDF §8 and §10 do** — PDF wins → SCOPE-027 and SCOPE-030 (seat map viz) stay REQUIRED.  
4. Protocol `HOD_VERIFICATION` status is an implementation sketch, not a PDF-named status — do not invent PDF requirement for that label.

---

## 7. Remediation queue after freeze (for later phases — do not implement now)

**Must remediate (REQUIRED + GAP/PARTIAL blocking) — remaining after C2–C9:**

1. SCOPE-028 — paper exchange detection → **final AI phase**  
2. SCOPE-027 — learned posture Correct/Incorrect classifier → **final AI phase**  
3. ~~SCOPE-009 / camera ID on case~~ — **done (C5)**  
4. SCOPE-030 seat-map visualization — PDF REQUIRED; **project decision (C11-B §12): EXCLUDED from implementation**  
5. SCOPE-002/032 — strengthen custom YOLO path for watches/notes → **final AI phase**

**May remediate (PARTIAL) — remaining:**

6. ~~Exam Dept semester-wise trends (SCOPE-017)~~ — **done lite (C7)**  
7. ~~Audit structured reports (SCOPE-025)~~ — **done lite (C9 CSV export)**; no PDF/IP/UA/diffs/crypto  
8. MediaPipe availability (SCOPE-026) — env/Python wheel  
9. ~~Notification routing audit for Exam/UFM on create (SCOPE-020)~~ — **done (C4)**

**Do not remediate as scope (OUT OF SCOPE / FUTURE):**

- PKI, SIS, SSO, WebRTC, AU paper-form parity, PDF export engine, campus fleet certification as a product feature

---

## 8. Phase A stop statement

- Official PDF **was located and fully inspected** (13 pages).  
- Authoritative freeze is based on that PDF.  
- **No application code, schema, or workflow changes were made in Phase A** (this file is documentation only).  
- Awaiting further instructions before any remediation phase.

---

## 9. Sign-off checklist (human)

- [ ] Supervisor confirms PDF file used is the approved submission version  
- [ ] Supervisor confirms PKI is NOT required (digital name+ack OK)  
- [ ] Supervisor confirms SIS is OUT OF SCOPE for FYP  
- [ ] Supervisor confirms seat-map UI remains REQUIRED  
- [ ] Supervisor confirms learned posture DL remains REQUIRED  
- [ ] Stakeholder accepts OUT OF SCOPE list in §5  

---

## 10. Phase C8 reassessment — manual result-hold UI (documentation only)

**Question:** Does the authoritative/current scope require a separate **manual** result-hold create UI (beyond automatic hold on UFM APPROVE)?

**Authoritative requirement (SCOPE-023 / PDF §5.1):** result hold, transcript blocking, and **controlled release after final decision**. Status already **COMPLETE** via local `ResultControl`.

**What the product already does:**

1. When UFM Committee (workflow) sets a case to **APPROVED**, the backend auto-creates a `ResultControl` (`result_status=HELD`, `transcript_status=BLOCKED`), audits `RESULT_HOLD_CREATED`, and notifies Exam Department.  
2. Authorized staff use **Result Holds** (`/app/result-controls`) to **list** holds and **release** them (`RESULT_RELEASED`).  
3. A staff API `POST /result-controls` exists for exceptional manual creation; it is **not** a frozen PDF-required product surface. No separate “create hold” screen is mandated.

**Decision:** A separate manual result-hold **create** UI is **NOT REQUIRED**. Implementing one would be speculative checklist polish, not scope completion. Do not invent a new requirement.

**C8 outcome:** INTENTIONALLY NOT REQUIRED — no functional code changes for this phase.

---

## 11. Phase C10 — non-AI integration / regression checkpoint

**Date:** 2026-09-30  

Host verification: full `pytest -q` **235 passed**; frontend `npm run build` OK; `reportStats` node tests **7 passed**.  
Alembic script head: `20260930_0005_case_camera`. Live Postgres `alembic current` **not verified** (local auth failure).  

C2–C9 non-AI remediations are reflected in §4 statuses above. Remaining REQUIRED gaps from the PDF are primarily **final AI phase** items (paper exchange, learned posture, custom YOLO). Environmental items (MediaPipe wheel, SMTP, Docker host proof) remain host-dependent.

---

## 12. Phase C11-B — project decision: seat-map visualization excluded

**Date:** 2026-10-01  

**Conflict recorded:** VigilantEye Scope Document.pdf (§10 / SCOPE-030) still lists **seat-map visualization** as a REQUIRED team deliverable.  

**Current project decision (authoritative for implementation):** seat-map visualization is **explicitly NOT implemented** in this FYP build. C11-B / C11-C must **not** implement seat-map UI, SIS seating integration, or pretend the PDF never required it.

| Item | PDF freeze | Project decision |
|------|------------|------------------|
| Seat-map visualization (SCOPE-030) | REQUIRED | **EXCLUDED from implementation** |
| `seat_location` metadata string | OPTIONAL/CONDITIONAL | Kept as-is when present |
| Institutional SIS seating DB | FUTURE | Unchanged FUTURE |

Supervisor checklist item “seat-map UI remains REQUIRED” in §9 is **superseded for delivery** by this project decision; the PDF conflict remains documented for honesty.

---

## 13. Phase C11-C — professional UI/UX refactor

**Date:** 2026-10-01  

Professional frontend refactor of shared design primitives, AppLayout/sidebar/header, role-aware dashboards, cases list/detail, monitoring/evidence surfaces, reports tables, and responsive/mobile presentation.

**Preserved unchanged:** C11-B RBAC / route gates / backend authorization; C2–C10 business behavior; AI features; seat-map visualization (still excluded).

**Not claimed:** deployment, full project completion, or AI phase start.

---

## 14. Phase C11-D — final non-AI QA gate

**Date:** 2026-10-01  

Role-by-role / route / RBAC static verification; targeted UI access fixes; automated regression (`pytest`, role-access suite, `npm run build`).

**Fixes in C11-D:**
- Notification deep-links no longer send unauthorized roles to `/app/detections` or `/app/result-controls`.
- Help quick links / FAQ corrected for Admin / DEC / UFM monitoring access.

**Verified automated:** backend suite + C11-B role tests + frontend build.  
**Partial browser:** login page at desktop + ~390px mobile (preview; auth config requires live API).  
**NOT VERIFIED interactively:** full authenticated role walkthroughs / tablet matrix without live backend session.

**AI / seat-map:** still not implemented. Gate decision recorded in C11-D report.

---

## 15. Invigilator access cleanup (post C11-D)

**Date:** 2026-10-01  

Invigilator no longer has the standalone modules:

- Students directory (`/app/students`)
- Reports (`/app/reports`)
- Exam Setup / Master Data (`/app/master-data`)

Invigilator remains limited to: Dashboard, Live Monitoring, Detections & Alerts, My Cases, Report UFM Incident, Evidence Library, Notifications, Profile.

Read-only `GET /students` and exam/camera catalog APIs remain available for **Report UFM Incident** selectors and monitoring only — not as a directory/setup UI.

**END OF FROZEN SCOPE BASELINE**
