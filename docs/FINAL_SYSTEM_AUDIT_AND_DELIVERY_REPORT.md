# VigilantEye — Final System Audit & Delivery Report

## 1. Executive Summary

VigilantEye was subjected to a full pre-delivery audit against the authoritative role model (C11/C22/C26/C26-FIX/C27/C28), workflow (C17), result control (C16), filing (C15), and excluded/deferred scope.

**Verdict: READY WITH LIMITATIONS**

Critical RBAC and workflow boundaries for Invigilator-only monitoring/create/evidence-upload, report permissions, C22 queues, lifecycle, and result holds are **server-enforced and regression-tested**. Two real security/workflow defects were found and fixed during this audit (downstream `CASE_OPENED` mutation; Invigilator case/evidence IDOR). Full multi-role browser click-through was **not** possible because live auth is Google-only with password login disabled.

---

## 2. Audit Date

**2026-10-04** (Asia/Karachi local calendar date for delivery session)

---

## 3. Repository / Commit / Version Inspected

| Item | Value |
|------|--------|
| Project path | `C:\Users\KING\Desktop\NEW PROJ\Vigilant Eye` |
| Branch ref | `refs/heads/main` |
| Commit SHA (`.git/refs/heads/main`) | `d19901a4de7ee52ffa637adef638b31e0be6289c` |
| Note | Host `git` CLI unavailable in audit shell; SHA read from git refs file. Working tree includes audit fixes after this tip (see §32). |

---

## 4. Environment Inspected

| Component | Evidence |
|-----------|----------|
| Dev Compose | `docker-compose.yml` — `vigilanteye-api-1`, `vigilanteye-frontend-1`, `vigilanteye-db-1` **Up / healthy** |
| API | `http://127.0.0.1:8000` — `/health` → `ok`; `/ready` → migrations current |
| Frontend (dev) | `http://localhost:5173` — Vite bind-mount |
| Auth | `AUTH_MODE=google`, `PASSWORD_LOGIN_ENABLED=0`, `ENABLE_DEMO_SEED=0` |
| `/auth/config` | `google_auth_enabled=true`, `password_login_enabled=false`, `demo_helpers_enabled=false` |
| Alembic | `alembic_current` = `alembic_head` = `20260930_0005_case_camera`; `migrations_pending=false` |

---

## 5. Scope Verification

Authoritative docs read: Scope PDF (via FROZEN baseline), Master Protocol references, `REQUIREMENTS_TRACEABILITY.md`, `SCOPE_COVERAGE.md`, C16/C17/C18/C19, plus C11–C28 implementation in code.

| Decision | Status in delivery |
|----------|-------------------|
| Seat-map visualization | **EXCLUDED** (not implemented; not reopened) |
| AI implementation / custom YOLO training | **DEFERRED** (assistive detections only; no autonomous decisions) |
| Learned posture classifier | **DEFERRED** |
| Paper-exchange detection | **DEFERRED** |
| SIS / Campus SSO / WebRTC / PKI / PDF engine / crypto audit chain / AU paper form | **EXCLUDED / FUTURE** |
| Admin = non-operational | **PASS** (nav + API isolation) |
| HOD ≠ monitoring / ≠ case create | **PASS** (C26-FIX) |
| Exam Department ≠ monitoring | **PASS** (C26) |
| Evidence upload = Invigilator only | **PASS** (C28) |
| Reports ≠ monitoring permissions | **PASS** (C27) |

---

## 6. Requirements Traceability Summary

| Requirement | Source | Backend | Frontend | RBAC | Tests | Status | Remaining limitation |
|-------------|--------|---------|----------|------|-------|--------|----------------------|
| Live monitoring | SCOPE-001 / R01 | `/live/*`, MONITOR_ROLES | `/app/monitoring` | Invigilator | c11b, c26fix, authz11 | **PASS** | Fleet/RTSP ops env-dependent |
| Detections | SCOPE-002–004 | DETECTION_STAFF_ROLES | `/app/detections` | Invigilator | c11b, c28 | **PASS** | Custom YOLO deferred |
| Case create + filing | C15 / SCOPE-014 | `POST /ufm-cases` Invigilator | CreateCase | CASE_CREATE | c15, c11b | **PASS** | — |
| Workflow HOD→DEC→Exam→UFM | SCOPE-015–018 / C17 | `workflow.py` | CaseDetail actions | Review roles | lifecycle, c17, c22 | **PASS** | Return → PENDING (HOD), not previous-only |
| Student clarification | SCOPE-019 | Student APIs | Clarification | STUDENT | c11b, lifecycle | **PASS** | One-shot |
| Notifications | SCOPE-020 / C4 | notify helpers | Notifications | Role queues | email/lifecycle suites | **PASS** | SMTP optional / mock |
| Result hold on APPROVE | C16 / SCOPE-023 | Auto hold + release | Result Holds | Exam+UFM | c16 | **PASS** | No SIS; no manual Place Hold UI |
| Audit + CSV | SCOPE-025 / C9 | Audit APIs | Audit Trail | Ops roles | c9, c23 | **PASS** | Not crypto-immutable |
| Reports + case CSV | C6/C7/C27 | REPORTS_ROLES | Reports | Staff+Inv | c6,c7,c27 | **PASS** | No PDF engine |
| C22 queue visibility | C22 | status maps on list | Dashboard queues | Server filter | c22 | **PASS** | Reviewers may still GET by ID for institutional records |
| Seat map | PDF §10 | — | — | — | — | **EXCLUDED** | Project decision |
| Paper exchange / learned posture / custom YOLO | PDF / C19 | Partial rules | Overlay only | — | policy tests | **DEFERRED** | Final AI phase |
| Admin ops | C11-B | Admin routers | `/app/admin/*` | ADMINISTRATOR | admin phases | **PASS** | Non-operational |

Classification legend used: **PASS / PARTIAL / FAIL / EXCLUDED / DEFERRED / UNVERIFIED**.

---

## 7. Role / RBAC Audit

### Authoritative sets (code)

| Set | Value |
|-----|--------|
| `MONITOR_ROLES` | `{INVIGILATOR}` |
| `DETECTION_STAFF_ROLES` / FE `DETECTION_ROLES` | `{INVIGILATOR}` |
| `CASE_CREATE_ROLES` | `{INVIGILATOR}` |
| `EVIDENCE_UPLOAD_ROLES` | `{INVIGILATOR}` |
| `REPORTS_ROLES` | Invigilator, HOD, DEC, Exam, UFM |
| `RESULT_CONTROL_ROLES` | Exam, UFM |
| `OPERATIONAL_AUDIT_ROLES` | HOD, DEC, Exam, UFM |

### Forbidden operations (API tests)

| Role | Action | Expected | Evidence |
|------|--------|----------|----------|
| HOD | `POST /ufm-cases` | 403 | `test_role_access_c11b` / c26fix |
| HOD | `/live/status`, detections | 403 | c11b, c26fix |
| HOD | `POST /evidence` | 403 | c28 |
| DEC / Exam / UFM | case create / live / detections / evidence upload | 403 | c11b, c27, c28 |
| STUDENT | staff cases / create / monitor / detections / upload | 403 | c11b, authz10 |
| ADMINISTRATOR | operational UFM | denied | c11b + admin nav |

Frontend route gates in `App.jsx` + `navByRole.js` match these sets; backend `require_roles` is the security boundary.

---

## 8. Case Lifecycle Audit

Verified by `workflow.py` + `tests/test_ufm_lifecycle_phase26.py` + `test_workflow_clarity_c17.py` + C22:

```
PENDING → (HOD open optional) UNDER_REVIEW → DEC_REVIEW → EXAM_DEPARTMENT_REVIEW
  → UFM_COMMITTEE_REVIEW → APPROVED | REJECTED
RETURN (allowed roles/statuses) → PENDING
```

| Check | Result |
|-------|--------|
| Valid forwards | **PASS** |
| Invalid role/action | **PASS** (denied) |
| Status skip / forge via body | **PASS** (server `next_status`) |
| Return → PENDING | **PASS** |
| Final lock | **PASS** |
| Audit + notifications on transitions | **PASS** |

**Fixed this audit:** `GET /ufm-cases/{id}` no longer lets DEC/Exam/UFM mutate `PENDING → UNDER_REVIEW` (HOD-only `CASE_OPENED`).

---

## 9. Case Creation Audit (C15)

| Check | Status |
|-------|--------|
| Select / search student + exam | **PASS** (API + CreateCase UI) |
| Manual filing student/exam | **PASS** (filing-time only; audited) |
| No duplicate student on roll match | **PASS** (tests) |
| `user_id` injection on manual filing | **PASS** (guarded) |
| Server `created_at` authoritative | **PASS** (C20) |
| Latest-first ordering | **PASS** (C21) |

---

## 10. Evidence Audit (C28)

| Check | Status |
|-------|--------|
| Invigilator upload | **PASS** |
| HOD/DEC/Exam/UFM upload | **403 PASS** |
| View permitted evidence | **PASS** |
| Student own-case only | **PASS** |
| Path traversal hardening | **PASS** (existing security suites) |
| Invigilator cross-case evidence list/detail | **FIXED** — own reported cases (+ orphans for attach) |

---

## 11. Result-Control Audit (C16)

| Action | Result control | Status |
|--------|----------------|--------|
| APPROVE | Auto On Hold / transcript Blocked | **PASS** |
| RETURN / REJECT / FORWARD | No RC create/release | **PASS** |
| RELEASE | Exam + UFM only + confirm UI + audit | **PASS** |
| Student release | Denied | **PASS** |
| Manual Place Hold UI | Absent (excluded) | **PASS** |

---

## 12. Reports / CSV Audit (C27)

| Check | Status |
|-------|--------|
| Reports use `REPORTS_ROLES` (not MONITOR/DETECTION/CREATE) | **PASS** |
| Invigilator CSV = own reported cases | **PASS** |
| Reviewer CSV institutional | **PASS** |
| Student / Admin operational reports | Denied / out of ops nav | **PASS** |
| Dept/semester stats + unknown values | **PASS** (`reportStats.test.mjs` 7/7) |

---

## 13. Audit-Log Audit

Coverage includes case create/sign, filing-time student/exam, reviews, evidence upload, result hold/release, clarification, admin events (existing suites + c9/c23). Unauthorized actions do not mint misleading success audits.

CSV audit export remains ops-role gated.

---

## 14. Notification Audit

C4 recipients preserved (create → HOD/Exam/UFM/student; status/action/result notifications per workflow). Inactive users excluded where implemented. FE destination helpers respect detection/report role gates. Full live SMTP delivery **NOT VERIFIED** (credentials optional; mock path exists).

---

## 15. Student Audit

| Check | Status |
|-------|--------|
| Own cases / status / notifications / clarification | **PASS** (API tests) |
| One-shot clarification | **PASS** |
| No staff routes/nav | **PASS** |
| Quick Links removed; C25 FAQ trim; Sign-in Method removed | **PASS** (`test_help_student_faq_c24`) |
| Invented “3 working days” deadline in guidelines | **FIXED** this audit |

Browser student walkthrough: **NOT VERIFIED** (Google-only auth).

---

## 16. Admin Audit

Admin nav = users/import/roles/admin audit/students directory/system/profile. No monitoring/create/review. Direct URL to ops pages gated. API admin boundaries covered by admin phase tests.

---

## 17. Dashboard Audit

Role dashboards answer role / queue / next action via C17 presentation + C22 scopes. Only Invigilator sees Live Monitoring / Detections / Create Case. HOD/DEC/Exam/UFM see review/records/result controls as modeled. KPI/list ordering latest-first (C21).

---

## 18. Route Audit

Enumerated from `App.jsx` + `navByRole.js`. Ops routes wrapped in `OpsRoles` / `Operational` / `AdminOnly`. Unauthenticated `/app/monitoring` → redirect `/login` (**browser verified**).

| Route | Intended | Notes |
|-------|----------|-------|
| `/app/monitoring`, `/app/detections`, `/app/cases/new` | Invigilator | Gates + API |
| `/app/evidence` | View roles (upload Inv only) | C28 |
| `/app/reports` | REPORTS_ROLES | C27 |
| `/app/result-controls` | Exam + UFM | C16 |
| `/app/audit` | Ops audit roles | — |
| `/app/users` | Redirect away | Admin uses `/app/admin/users` |
| `/app/master-data` | DEC view only | Create UI empty |
| `/app/help` | All authenticated | Role-specific FAQ |

---

## 19. Responsive / UI Audit

C13/C14 tests + design system present. Full multi-viewport visual pass (1440/1280/1024/768/390) **NOT VERIFIED** in authenticated browser this session. Production bundle builds cleanly; chunk >500KB warning only (non-blocking).

Fixes this audit: empty-camera copy no longer incorrectly directs Invigilators to Exam Department; staff Help guidelines aligned with Invigilator-only monitoring.

---

## 20. Accessibility Audit

Semantic buttons/links, PageHeader patterns, dialogs, and role=alert error regions exist. Full keyboard/screen-reader matrix **NOT VERIFIED** interactively this session. No intentional clickable-div primary actions introduced.

---

## 21. API / Backend Audit

AuthN + `require_roles` + object checks on cases/evidence. Workflow transitions server-side with row lock. Pagination not universal on all lists (known product limitation for large institutions). Deprecation warnings for `datetime.utcnow()` present — non-blocking.

---

## 22. Database / Migration Audit

| Check | Result |
|-------|--------|
| `/ready` migrations_pending | `false` |
| Head | `20260930_0005_case_camera` |
| Fresh DB migrate | **NOT VERIFIED** this session (existing volume healthy) |
| Destructive migration | None observed at head |

---

## 23. Docker / Deployment Audit

| Check | Result |
|-------|--------|
| Dev stack up + healthy | **PASS** |
| API health/ready | **PASS** |
| Frontend Vite serve | **PASS** |
| Frontend `npm run build` | **PASS** |
| Prod compose file present | **PASS** (`docker-compose.prod.yml`) |
| Prod compose validate without `.env.production` | Fails as designed (missing `CORS_ORIGINS` etc.) |
| Prod full `up --build` | **NOT VERIFIED** |
| Secrets in git | `.env` gitignored; `.dockerignore` excludes `.env` |
| Postgres host port exposed | Dev + prod scaffold map `15432` — ops risk if left open |
| TLS terminator | **Not in repo** |

---

## 24. Security Audit

| Finding | Severity | Disposition |
|---------|----------|-------------|
| DEC/Exam/UFM `GET` mutated PENDING→UNDER_REVIEW | P0/P1 | **FIXED** (HOD-only) |
| Invigilator could open other reporters’ cases by ID / browse their evidence | P1 | **FIXED** |
| Google-only; no password fallback in live env | — | Intended |
| JWT/DB secrets in local `.env` | Ops | Gitignored; must rotate for university deploy |
| CORS / prod secrets | Ops | Required via `.env.production` |
| Hardcoded `password123` / `admin123` in app source | — | **Not found** |
| AI autonomous approve/reject/release | — | **Absent** |

---

## 25. Error-Handling Audit

API returns HTTP error details without stack traces to clients in normal paths. FE shows role=alert / inline errors. Full offline/timeout matrix **PARTIALLY** covered by existing UX patterns; not fully browser-retested this session.

---

## 26. Performance Observations

- Full pytest ~5–6 minutes in container (acceptable).
- Frontend main JS ~563 KB / ~147 KB gzip — code-split opportunity only.
- Dashboard polls + WebSocket for detections — acceptable for demo scale.
- No P0 performance defect fixed (none material).

---

## 27. Test Results

### Backend (full)

```text
Command: docker exec -w /app/backend vigilanteye-api-1 pytest -q --tb=line
Result:  334 passed, 3 skipped, 2109 warnings in 346.19s
```

(Pre-fix baseline earlier same session: `333 passed, 3 skipped` — +1 new regression test.)

### Focused security/workflow after fixes

```text
Command: pytest -q tests/test_case_visibility_c22.py tests/test_evidence_upload_c28.py
         tests/test_role_access_c11b.py tests/test_hod_scope_c26fix.py
         tests/test_reports_access_c27.py tests/test_ufm_lifecycle_phase26.py
         tests/test_result_control_c16.py tests/test_help_student_faq_c24.py
Result:  53 passed
```

### Frontend

```text
Command: npm run build  (frontend/)
Result:  PASS — vite production build (~0.7–1.2s)
Command: node --test src/config/reportStats.test.mjs  (in frontend container)
Result:  7 passed, 0 failed
```

### Readiness

```text
Command: curl http://127.0.0.1:8000/ready
Result:  migrations_pending=false; head=20260930_0005_case_camera
```

---

## 28. Browser / Live Verification Results

| Check | Result |
|-------|--------|
| Open `http://localhost:5173/login` | **PASS** — VigilantEye Google sign-in only |
| Unauthenticated `/app/monitoring` | **PASS** — redirects to `/login` |
| Per-role click-through (Inv/HOD/DEC/Exam/UFM/Student/Admin) | **NOT VERIFIED** — Google OAuth required; password login disabled |
| Claim | Browser E2E **incomplete by environment** |

API-level RBAC/lifecycle/result/evidence/report suites substitute for interactive role login.

---

## 29. Development-Artifact Scan

| Pattern | Finding |
|---------|---------|
| `TODO`/`FIXME`/`HACK` in FE src | None material |
| `console.log` in FE src | None |
| `Coming Soon` / `Lorem ipsum` | None in app src |
| `password123` / `admin123` | None |
| Test passwords (`Demo@123`, etc.) | Legitimate test fixtures |
| `localhost` in compose/docs | Legitimate local demo |
| SCOPE_COVERAGE “Invigilator has no … Reports UI” | **Stale doc wording** vs C27 (Invigilator has Reports) — documentation drift, not runtime bug |

---

## 30. AI Boundary Verification

- Detections assist Invigilators; draft case requires human create/sign-off.
- No AI path calls `APPROVE` / `REJECT` / result release / disciplinary finalization.
- Custom training / paper-exchange / learned posture remain **deferred** (C19 plan only).

---

## 31. Issues Found

1. **P0/P1** — Downstream reviewers opening `PENDING` case via GET forced `UNDER_REVIEW`.
2. **P1** — Invigilator case detail/evidence not ownership-scoped (list was; detail was not).
3. **P2** — Student Help guideline invented “3 working days” deadline.
4. **P2** — Empty monitoring cameras message incorrectly blamed Exam Department.
5. **P3** — `SCOPE_COVERAGE.md` Invigilator Reports line outdated vs C27.
6. **Limitation** — Google-only auth blocks full browser role matrix.
7. **Limitation** — Prod TLS / hardened DB exposure / institutional SMTP not packaged.
8. **Deferred/Excluded** — Seat map, AI upgrades, SIS, SSO, PDF, PKI (by decision).

---

## 32. Issues Fixed

| Fix | Files |
|-----|-------|
| HOD-only `CASE_OPENED` | `backend/main.py` |
| Invigilator ownership on case access | `backend/case_access.py` |
| Invigilator evidence list/upload ownership | `backend/main.py` |
| Regression tests | `backend/tests/test_case_visibility_c22.py` |
| Student guideline deadline | `frontend/src/pages/HelpPage.jsx` |
| Staff Help + empty-camera copy | `HelpPage.jsx`, `MonitoringPage.jsx` |

Container synced via `docker cp` + API restart for pytest evidence.

---

## 33. Remaining Limitations

1. Full authenticated multi-role browser E2E not run (Google OAuth).
2. Production compose not end-to-end deployed/TLS-terminated in this audit.
3. SMTP live delivery depends on institutional credentials.
4. AI detection quality depends on COCO/fallback — custom model deferred.
5. MediaPipe may be unavailable on some Python builds (OpenCV fallback).
6. Reviewing staff can still open case-by-ID outside active-queue filters (institutional records); list/active scopes remain enforced.
7. Master-data **API** still allows HOD/Exam create endpoints while FE create UI is emptied — intentional FE cleanup; API hardening beyond current role catalog was not invented.
8. Some living docs (e.g. older C18 HOD monitoring notes, SCOPE_COVERAGE Reports line) are historically stale relative to C26/C27 code.

---

## 34. Explicit Excluded / Deferred Features

- Seat-map visualization  
- AI implementation phase / custom YOLO integration  
- Learned posture classifier  
- Paper-exchange detection  
- SIS integration  
- Campus SSO  
- WebRTC mesh  
- PKI / cryptographic signatures  
- PDF report engine  
- Cryptographically immutable audit chain  
- Official AU paper UFM form  

---

## 35. Final Delivery Status

# **READY WITH LIMITATIONS**

Not “READY FOR UNIVERSITY DELIVERY” without caveat, because:

- Browser role E2E unverified under Google-only auth  
- Production TLS/ops hardening not demonstrated  
- Deferred AI quality items remain (accepted exclusions, but they affect “complete vs PDF ideal”)  

For the **implemented non-AI institutional portal scope** with documented exclusions, the system is delivery-capable with the limitations above.

---

## 36. Exact Recommended Next Step

1. Provision university Google accounts for all seven roles and run the DEMO_RUNBOOK click-through once on the target host.  
2. Create `.env.production` from the example; set strong `JWT_SECRET` / DB password / `CORS_ORIGINS`; keep Postgres off the public internet; place TLS reverse proxy in front of frontend/API.  
3. Optionally tighten master-data write APIs to Administrator-only if stakeholders confirm that FE cleanup should become the server rule.  
4. Keep AI/seat-map items for a separate phase; do not reopen them in this delivery package.

---

## FINAL ACCEPTANCE GATE

**Date:** 2026-10-04 (continuation of final pre-delivery session)  
**Production auth after gate:** `AUTH_MODE=google`, `PASSWORD_LOGIN_ENABLED=0` (restored)

### Notifications

- **EMAIL_MOCK:** **PASS** — `tests/test_email_phase24.py` (26 tests): portal notification records, recipient rules (incl. inactive exclusion), workflow/clarification paths, SMTP failure does not roll back DB work, secrets not exposed in status/API/frontend bundle.
- **Real SMTP:** **NOT VERIFIED (delivery)** — SMTP host/auth configured (`smtp.gmail.com`, auth present). Acceptance script `scripts/acceptance_smtp_gate.py` reached SMTP DATA and received `SMTPDataError` (provider rejected message; historically consistent with Gmail daily sending limits). **Do not treat as PASS.** No credentials printed.
- **SMTP failure handling:** **PASS** — invalid host returns `error` / `gaierror` category without secrets; workflow/notification commit path remains consistent with Phase 24 design (email after commit; failures logged safely).
- **Status:** **PASS WITH LIMITATION** (mock + failure handling verified; live mailbox delivery not confirmed)

### Responsive UI

Browser matrix executed against live Vite UI (authenticated via temporary `AUTH_MODE=both` for acceptance only; production Google restored afterward).

| Viewport | Result |
|----------|--------|
| 1440×900 | **PASS** — UFM/DEC major pages; tables shown; no page horizontal overflow |
| 1280×800 | **PASS** — card↔table switch at 1280; no page overflow |
| 1024×768 | **PASS** — mobile/tablet cards (`flex`), desktop tables `none`; no page overflow |
| 768×1024 | **PASS** — same card pattern; no page overflow |
| 390×844 | **PASS** — Invigilator (incl. Create UFM Case), Student, HOD, Exam Dept, Admin Users, UFM, Login; no page overflow |

- **Status:** **PASS** — no material unresolved layout defects found in probed pages. Table horizontal scroll remains inside `.portal-table-wrap` only (by design).

### Accessibility

- **Keyboard:** **PASS WITH NOTES** — sidebar toggle + `inert` when closed; shared `ConfirmDialog` Tab cycle / Esc / focus return; Case Detail review/release dialogs upgraded to the same focus pattern this gate.
- **Focus:** **PASS** — `:focus-visible` design system present; sidebar/header controls labeled; dialogs move focus to Cancel and restore prior focus on close.
- **Forms:** **PASS** — Create UFM Case at 390×844: 29 labels, 0 unlabeled inputs; sign-off field labeled (regression test).
- **Dialogs:** **PASS** — `role="alertdialog"` / `role="dialog"` + `aria-modal` + accessible names; Esc closes Case Detail confirms.
- **Tables:** **PASS** — desktop tables / mobile cards; header semantics retained on desktop; cards keep primary actions.
- **Screen-reader semantics:** **PASS** — notifications `aria-label` includes unread count; loading/error patterns retained; no new clickable-div primary actions introduced.
- **Color/contrast:** **PASS** — status still uses text labels/badges (not color alone); no palette redesign.
- **Reduced motion:** **PASS** — `prefers-reduced-motion` rules present in `index.css`.
- **Status:** **PASS**

### Browser E2E

- **Roles actually tested (authenticated browser):** Invigilator, HOD, DEC, Exam Department, UFM Committee, Student, Administrator — plus Login (Google-only) unauthenticated.
- **Roles not tested under permanent Google OAuth click-through:** all seven (Google account matrix not available in this environment).
- **Reason:** Production compose uses Google-only auth. Multi-role UI matrix used **temporary** `AUTH_MODE=both` + demo password login for acceptance, then restored `AUTH_MODE=google`. Compensating coverage: C11–C28 API/RBAC pytest suite.
- **Status:** **PASS WITH DOCUMENTED AUTH LIMITATION**

### Regression

- **Backend:** `docker exec -w /app/backend vigilanteye-api-1 pytest -q` → **340 passed, 3 skipped**
- **Frontend:** `npm run build` → **PASS** (chunk >500KB warning only)
- **Focused tests:** `test_email_phase24.py`, `test_a11y_acceptance.py`, `test_layout_c14.py` → **PASS**; `node --test src/config/reportStats.test.mjs` → **7 passed**
- **Build:** PASS

### Acceptance fixes in this gate

| Fix | Files |
|-----|-------|
| Case Detail confirm/release focus trap, Esc, focus return | `frontend/src/pages/CaseDetailPage.jsx` |
| A11y regression for Case Detail dialogs + prior ConfirmDialog/Sidebar/Header markers | `backend/tests/test_a11y_acceptance.py` |
| Table card switch at 1280 (tablet usability) | `frontend/src/index.css`, `backend/tests/test_layout_c14.py` |
| Shared ConfirmDialog focus management; sidebar `inert`; header `aria-expanded` | `ConfirmDialog.jsx`, `Sidebar.jsx`, `Header.jsx` |
| SMTP acceptance helper (safe logging) | `backend/scripts/acceptance_smtp_gate.py` |

### Final acceptance verdict

# **READY WITH LIMITATIONS**

Not unconditional “READY FOR UNIVERSITY DELIVERY” because:

1. **Real SMTP mailbox delivery was not verified** (`SMTPDataError` / provider rejection after configured auth).  
2. **Full Google-account browser E2E** for all roles remains an operational step outside this environment (temporary `both` used only for acceptance probing).

For the implemented non-AI portal scope, with EMAIL_MOCK as the supported non-SMTP path and responsive/a11y gates closed, the system remains delivery-capable under these documented limitations.

