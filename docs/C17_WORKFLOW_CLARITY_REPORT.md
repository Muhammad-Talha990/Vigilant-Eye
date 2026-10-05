# C17 — Final UFM Workflow Consistency, Action Clarity & End-to-End UX Gate

## C17 STATUS

**COMPLETE WITH LIMITATION** (live multi-role browser walkthrough not re-authenticated in this session; API/tests/build verified).

## WORKFLOW VERIFIED

Authoritative sources: `backend/workflow.py`, `STATUS_NEXT_ROLE` in `main.py`, `docs/UNIVERSITY_OPS.md`, C16 report, DEMO_RUNBOOK.

```
PENDING / UNDER_REVIEW  — HOD FORWARD → DEC_REVIEW
DEC_REVIEW              — DEC FORWARD → EXAM_DEPARTMENT_REVIEW
EXAM_DEPARTMENT_REVIEW  — Exam FORWARD → UFM_COMMITTEE_REVIEW
UFM_COMMITTEE_REVIEW    — APPROVE → APPROVED | REJECT → REJECTED

RETURN (HOD / DEC / Exam Department from allowed statuses) → PENDING
  → next notified/responsible role = HOD
```

**Doc vs code:** Informal “return to previous role” language must not override implementation. Ops docs + code: Return → **Pending** (HOD restarts chain).

Optional `UNDER_REVIEW` remains in the model; HOD may Forward from Pending directly to DEC Review.

## CHANGES MADE

| File | Why |
|---|---|
| `frontend/src/config/workflowPresentation.js` | Single presentation mirror of real WORKFLOW + next-role + result-impact copy |
| `frontend/src/config/reviewActions.js` | Delegate to shared mirror (no drift) |
| `frontend/src/pages/CaseDetailPage.jsx` | “What happens next?” panel; action button hints; confirm shows after-status / next role / result impact; student stage copy |
| `backend/main.py` | Clearer notification wording (same recipients/types); human status labels |
| `backend/tests/test_workflow_clarity_c17.py` | Mirror + Return/Forward/final + UI markers |
| `docs/C17_WORKFLOW_CLARITY_REPORT.md` | This report |

## RETURN BEHAVIOR

- Who: HOD (from DEC_REVIEW / UNDER_REVIEW), DEC (from DEC_REVIEW / EXAM_DEPARTMENT_REVIEW), Exam Dept (from EXAM_DEPARTMENT_REVIEW / UFM_COMMITTEE_REVIEW)
- Resulting status: **PENDING**
- Next responsibility: **HOD** (not “previous reviewer only”)
- Notifications: reporter + linked student (CASE_STATUS); HOD role (CASE_ACTION_REQUIRED)
- Result control: **unchanged**
- Audit: `CASE_REVIEW_RETURN`

## FORWARD BEHAVIOR

- HOD → DEC_REVIEW (next: DEC)
- DEC → EXAM_DEPARTMENT_REVIEW (next: Exam Department)
- Exam → UFM_COMMITTEE_REVIEW (next: UFM Committee)
- Not final; no result-control change
- Audit: `CASE_REVIEW_FORWARD`

## APPROVE BEHAVIOR

- Final status **APPROVED**
- Auto result hold On Hold / transcript Blocked (C16)
- Notifies Exam Dept (RESULT_HOLD) + reporter/student status
- Audit: `CASE_REVIEW_APPROVE` + `RESULT_HOLD_CREATED`

## REJECT BEHAVIOR

- Final status **REJECTED**
- **No** result hold created
- Reporter/student status notifications
- Audit: `CASE_REVIEW_REJECT`

## RESULT CONTROL

C16 behavior preserved. Case Detail still separates case status vs result status; Approve confirm text states hold is created; Return/Reject/Forward state no RC change.

## NOTIFICATIONS

- Recipients unchanged (reporter, student, next role, Exam on hold).
- Copy improved: human status labels + “was …” previous status; action-required names next role.
- Destinations: case_id → case detail; RESULT_* → Result Controls for Exam/UFM (existing C11-aware helpers).

## AUDIT

No model change. Existing `CASE_REVIEW_*`, clarification, `RESULT_HOLD_CREATED`, `RESULT_RELEASED` retained. UI confirms sign-off is audited.

## RBAC

No role expansion. Review actions still HOD/DEC/Exam/UFM only; Result Controls Exam+UFM; Admin remains non-operational for UFM reviews.

## TEST RESULTS

- Backend focused + regression (C17, C16, lifecycle, C11b, C13, C14): **51 passed**
- C15 (`test_ufm_form_c15.py`): **passed** (re-run after C17)
- Frontend build: **✓ built in 3.18s**

## LIVE VERIFICATION

**LIVE VERIFICATION BLOCKED** for full multi-role browser walkthrough in this session (Google live auth / no interactive demo login performed here).

Still verified:
- Backend workflow tables + C17/C16/lifecycle/RBAC tests
- Frontend production build with new Case Detail / workflowPresentation modules
- Docker sync + API restart

Remains unverified interactively:
- Per-role click-through of confirm dialogs in browser at 390–1440 widths

## REMAINING LIMITATIONS

1. Return semantics can still surprise users who expect “previous reviewer” — UI now states Pending/HOD explicitly; backend unchanged.
2. Remarks remain optional in API (UI recommends them for Return).
3. No authenticated end-to-end browser pass logged in this session.
4. Scope PDF file was not present in the workspace tree; used frozen docs + code.

## AI STATUS

**NO AI IMPLEMENTED IN C17.**

## SEAT MAP

**SEAT MAP REMAINS EXCLUDED BY PROJECT DECISION.**
