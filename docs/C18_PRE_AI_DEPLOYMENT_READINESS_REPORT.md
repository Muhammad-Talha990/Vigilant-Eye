# C18 — Final Pre-AI Completeness & Deployment-Readiness Report

## 1. Final Status

**PRE-AI: READY WITH DOCUMENTED LIMITATIONS**  
**DEPLOYMENT: READY WITH LIMITATIONS** (local Docker development verified; production compose exists but TLS / host-exposed DB / secrets ops remain)

No AI, seat-map, SIS, SSO, WebRTC, PKI, or PDF engine work was implemented in C18.

## 2. Scope Completeness Matrix

| Area | Status | Evidence | Limitation |
|---|---|---|---|
| Live monitoring (MJPEG / webcam / file / RTSP) | COMPLETE WITH DOCUMENTED LIMITATION | Live routes + MONITOR roles; C11b denies DEC live | Environment-dependent camera/RTSP; no WebRTC mesh |
| Detections + alerts | COMPLETE WITH DOCUMENTED LIMITATION | Detections API/UI; WS alerts | Custom YOLO/chit training deferred |
| Draft/create UFM from detection | COMPLETE | CreateCase + draft endpoints; C15 tests | — |
| Flexible filing (C15) | COMPLETE | Manual/select student+exam; library evidence; filing-time only | Invigilator has no general master-data admin |
| Workflow HOD→DEC→Exam→UFM | COMPLETE | `workflow.py`; C17 clarity UI; lifecycle tests | Return → Pending (HOD), not previous-role-only |
| Digital sign-off | COMPLETE | Name+ack; not PKI | PKI deferred |
| Student clarification | COMPLETE | One-shot; student isolation tests | — |
| Notifications + optional email | COMPLETE WITH DOCUMENTED LIMITATION | Portal + SMTP/MOCK | SMTP needs credentials; Google-only live auth |
| Result control (C16) | COMPLETE | Auto hold on Approve; release Exam+UFM; no Place Hold UI | No `placed_by` column; audit-derived holder |
| Audit + CSV export | COMPLETE | Audit APIs/UI; C9 | No crypto immutability |
| Reports CSV / KPIs | COMPLETE | Reports roles; CSV export | No PDF engine |
| Admin users / import / roles | COMPLETE | Admin dashboard/actions; C11b | — |
| RBAC (C11-B) | COMPLETE | `test_role_access_c11b.py` + authz suites | Live browser Google login NOT VERIFIED this session |
| UI/UX C11-C / C13 / C14 | COMPLETE WITH DOCUMENTED LIMITATION | Design system; affordances; responsive cards | Full multi-viewport browser pass NOT VERIFIED |
| Workflow clarity C17 | COMPLETE | Case Detail “What happens next?” | — |
| Docker local | COMPLETE | Compose healthy; `/ready` at head | — |
| Docker production | COMPLETE WITH DOCUMENTED LIMITATION | `docker-compose.prod.yml` | No TLS; Postgres host port; ops seeds required |
| Seat-map / official AU PDF form | OUT OF CURRENT SCOPE | FROZEN_SCOPE / C17 | Excluded by decision |
| Learned posture / paper-exchange / custom YOLO | OUT OF CURRENT SCOPE | Traceability / protocol | Final AI phase |
| SIS / campus SSO / WebRTC / PKI | OUT OF CURRENT SCOPE | SCOPE_COVERAGE FUTURE | — |

## 3. Role-by-Role Verification

| Role | Verified via | Notes |
|---|---|---|
| INVIGILATOR | C11b + C15 + nav | Monitor, detections, create case; no students/exam-setup/reports/result release |
| HOD | C11b + lifecycle | Forward/Return; monitoring allowed; not admin |
| DEC | C11b + nav | Cases/evidence/reports/audit; **no** live monitoring nav |
| EXAM_DEPARTMENT | C11b + C16 | Process + result controls + release + monitoring |
| UFM_COMMITTEE | C11b + C16 | Final Approve/Reject + result controls |
| STUDENT | C11b + C16 case summary | Own cases/clarification/result status; no staff controls |
| ADMINISTRATOR | C11b + admin UI | Users/import/roles/audit/system; no UFM review actions |

## 4. UFM Lifecycle Verification

Verified by `workflow.py`, C17 report, and `test_ufm_lifecycle_phase26` / `test_workflow_clarity_c17`:

- Forward chain as documented
- **Return → PENDING → HOD**
- Approve / Reject terminal
- Clarification + notifications + audit retained

## 5. Result Control Verification

C16 behavior intact (tests green): Approve → On Hold; Return/Forward/Reject → no RC mutation; Release Exam+UFM only; no manual Place Hold UI.

## 6. Evidence & Monitoring Verification

- Evidence library + case link + access tests present (authz phase10)
- Monitoring infrastructure present; DEC denied live status (authz phase11)
- Custom AI detection deferred — current COCO/MediaPipe partial path remains as documented Partial

## 7. Notifications & Audit Verification

- Recipients unchanged; C17 humanized status wording
- Destinations role-aware (`notificationPresentation.js`)
- Audit CSV-only scope preserved

## 8. Reporting Verification

CSV + role-gated reports; no PDF engine.

## 9. RBAC & Security Verification

- Backend `require_roles` + frontend `OpsRoles` / `roleAccess.js`
- Production fail-fast: Google-only AUTH, JWT strength, CORS required
- C18 fix: pytest `conftest.py` forces `AUTH_MODE=both` for TestClient only (does not weaken live Google Compose)
- Live Google browser matrix: **NOT VERIFIED** this session

## 10. Database & Migration Verification

- Alembic head: `20260930_0005_case_camera`
- Live `/ready`: `migrations_pending: false`, DB ok
- Linear chain of 5 revisions; clean upgrade path via entrypoint

## 11. Docker & Deployment Verification

| Item | Result |
|---|---|
| Dev stack (`db`/`api`/`frontend`) | Running healthy |
| `/health` + `/ready` | OK |
| Prod compose | Present; nginx on 8080 |
| TLS | Not in-repo |
| Secrets | Local `.env` files exist; `.gitignore` now covers `.env.*` / production env files |

## 12. Responsive & Accessibility Verification

Prior C14/C13 work present in codebase. Fresh multi-breakpoint browser pass: **NOT VERIFIED** in C18.

## 13. Environment Dependencies

| Dependency | Required? | Notes |
|---|---|---|
| Docker + PostgreSQL | Yes (recommended) | Verified running |
| Python 3.12 (API image) | Yes | — |
| Node/Vite | Yes (dev) | Build verified |
| Google OAuth | Yes if AUTH_MODE=google | Current workspace live mode |
| SMTP | Optional | EMAIL_ENABLED / MOCK |
| Camera/RTSP | Optional | Monitoring |
| GPU / custom YOLO weights | No for non-AI gate | AI phase |

## 14. Tests

```
297 passed, 3 skipped (full backend pytest in API container)
Frontend: vite build OK (~3s)
Focused phases C11/C13–C17 included in full suite
```

Earlier false failures were caused by invalid `AUTH_MODE=hybrid` / Google Compose env without test override — fixed via `tests/conftest.py`.

## 15. Fixes Made During C18

1. `.gitignore` — ignore `.env.*` (including `.env.production`) while keeping `*.example`
2. `backend/tests/conftest.py` — force `AUTH_MODE=both` + password login for pytest under Google Compose
3. `README.md` — Alembic startup wording; pytest auth note
4. `docs/SCOPE_COVERAGE.md` — Docker status updated from Scaffold → Implemented (dev + prod scaffold)

No RBAC expansion, workflow changes, AI, or seat-map work.

## 16. Remaining Limitations

1. Production TLS / reverse-proxy not bundled
2. Postgres published on host in prod compose defaults
3. Live Google multi-role browser walkthrough not performed this session
4. MediaPipe/custom detection Incomplete by design until AI phase
5. Workspace may store real SMTP/JWT secrets locally — rotate if shared; never commit

## 17. Explicitly Deferred / Out of Scope

- Learned posture classifier, paper-exchange, custom YOLO/chit training
- Seat-map visualization
- Official AU UFM PDF form; PDF report engine
- PKI / cryptographic signatures; crypto-immutable audit
- SIS; campus SSO; WebRTC mesh

## 18. AI Readiness Decision

**B. READY FOR AI PHASE WITH DOCUMENTED LIMITATIONS**

Non-AI foundation (roles, lifecycle, filing, result control, audit, Docker dev) is substantially complete. Remaining items are documented exclusions/ops limitations, not blockers that reopen C11–C17.

## 19. Deployment Readiness Decision

**READY WITH LIMITATIONS**

- Local development: ready (Compose + `/ready` + build + tests)
- Campus/production deployment: requires operator TLS, secret management, Google user provisioning, optional SMTP — not “actually deployed” from this audit alone

## 20. Recommended Next Phase

Begin the **AI implementation phase** (custom detection / deferred ML) on this baseline without reopening non-AI workflow/RBAC unless a new defect appears. Keep C16 result-control and C17 Return→Pending semantics unchanged.
