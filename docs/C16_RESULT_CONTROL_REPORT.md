# C16 — Result Control Workflow & UX Clarification

## 1. Current result-control behavior discovered

| Capability | Status |
|---|---|
| Place hold (automatic) | **Yes** — on UFM Committee **APPROVE** only |
| Place hold (manual API) | **Yes** — `POST /result-controls` (Exam Dept + UFM Committee) |
| Place hold (portal UI) | **No** — intentionally out of scope (C8 / SCOPE-023) |
| Release hold | **Yes** — `PATCH /result-controls/{id}/release` |
| Auto-release | **No** |
| Linked to UFM case | **Yes** — unique `case_id` |
| Student / who / when | Model stores IDs + reason; release stores `released_by` / `released_at`; hold actor/time come from audit `RESULT_HOLD_CREATED` |
| Audit | `RESULT_HOLD_CREATED`, `RESULT_RELEASED` |

**Roles:** view / create / release = `EXAM_DEPARTMENT`, `UFM_COMMITTEE` only.

## 2. Root causes of UX confusion

1. List was hold-ID-first, not student-first.
2. Student name/roll depended on a fragile client-side join to `/ufm-cases`.
3. Result status used the same badge language as case status (“Result Hold” looked like another case state).
4. No case-detail Result Control section → users could not see hold vs case decision together.
5. Students saw case **Approved** with no explanation that a result hold applied.
6. No explicit explanation that RETURN / REJECT / FORWARD do not create or clear holds.
7. Manual place-hold was implied by empty-state copy even though portal UI does not support it.

## 3–7. Actual lifecycles (unchanged business rules)

| Event | Result control effect |
|---|---|
| **APPROVE** | Creates `HELD` / transcript `BLOCKED` if none exists; reason = automatic hold text |
| **RETURN** | No result-control create/update/release |
| **REJECT** | No result-control create/update/release |
| **FORWARD** | No result-control effect |
| **Release** | Authorized staff sets `RELEASED` / `ALLOWED`, records releaser + timestamp |

## 8–9. Who can place / release

- **Automatic place:** triggered by UFM Committee approve (actor recorded in audit).
- **Manual API place:** Exam Department, UFM Committee (no portal form — C8).
- **Release:** Exam Department, UFM Committee.
- **Other roles:** may see hold summary on a case they can open; cannot list/release via Result Controls API.

## 10. Exact UI changes

- **Result Controls page:** student-first list + detail; search; All / On Hold / Released filters; distinct On Hold badge; placed by/at from enrichment; release confirm named by student; workflow explainer; no place-hold form.
- **Case Detail:** Result Control section for all roles who can open the case (status-only for students; release for Exam/UFM).
- **Dashboard (Exam/UFM):** holds panel lists **student name** first + case link; clearer empty copy.
- Labels: `HELD` → **On Hold** (result-specific).

## 11. Backend changes

- `result_control_enrich.py` — join Student / UfmCase / AuditLog for display fields.
- Enriched `ResultControlOut` list/create/release responses.
- `result_control` summary nested on `UfmCaseOut` via `case_enrich`.
- Auto-hold audit `entity_id` corrected to **control.id** (was case.id).

## 12. RBAC verification

Covered by C16 tests + existing C11b: HOD 403 on release; Exam 200; Invigilator/Student cannot `GET /result-controls`.

## 13. Live verification

- Docker: `vigilanteye-api-1` restarted with enriched `main.py` / enrich modules.
- Docker: `vigilanteye-frontend-1` files synced; Vite production build succeeded.
- Manual UI paths to spot-check with Exam Dept / UFM Committee / Student demo accounts:
  - `/app/result-controls` — student-first list, filters, detail, release
  - Case detail — Result Control panel
  - Dashboard holds panel — student name first

## 14. Test results

```
45 passed (C16 + UFM lifecycle + layout C14 + role access C11b + UI affordance C13)
AUTH_MODE=hybrid EMAIL_ENABLED=0
```

C16-specific: 6/6 passed (enrichment, case summary, RETURN/REJECT no hold, release RBAC, UX markers).

## 15. Build result

```
vite build — ✓ built in 1.62s
```

## 16. Remaining limitations

- No `created_at` / `placed_by` columns on `result_controls` — placed by/at come from audit when present.
- No portal manual place-hold UI (approved C8 scope).
- Release notifies case reporter only (existing behavior).
- Client-side search/filter on full list (no list query params on backend).
