# Administrator user management (Phases 18–21)

## Principle

**Google authenticates identity. VigilantEye authorizes access.**

- A verified Google account does **not** receive a portal role from Google claims or JWT payload fields.
- Only an explicit `users` row (`email` + `role` + `is_active`) authorizes login.
- Unknown Google accounts receive `403 Account not authorized`.
- Domain membership never auto-registers anyone.
- Production authentication is **Google-only** — administrators never set portal passwords.
- Normal user management is done entirely in the Administrator UI — no Python, SQL, Docker, or `.env` edits for day-to-day account work.

## Operational separation

| Role | Workspace |
|------|-----------|
| **ADMINISTRATOR** | Access & system management only (`/app/admin/*`) |
| **INVIGILATOR** | Monitoring, detections, incident reporting |
| **HOD / DEC / EXAM_DEPARTMENT / UFM_COMMITTEE** | Their UFM workflow queues |
| **STUDENT** | Own cases, clarification, notifications |

Administrators **must not** see Live Monitoring, Detections, Cases, Evidence, Exam Setup, or other UFM operational navigation.

## How the university administrator creates an authorized portal account

1. Sign in as ADMINISTRATOR with Google (`Continue with Google`).
2. Open **Dashboard → + Add User** (or **Users → + Add User**).
3. Enter the person’s **exact Google email**, display **name**, and portal **role**.
4. Set **Active** (unchecked = authorized but cannot sign in yet).
5. For **STUDENT**, enter a **student roll** to link (or create) the student record. Staff roles do not need a roll.
6. Save. No portal password is created or emailed.
7. Tell the user to open the portal login page and click **Continue with Google** using that same Google email.
8. Backend verifies the Google ID token, finds the email in `users`, checks `is_active`, reads the **DB role**, and issues a JWT.
9. The user lands on the dashboard for their DB role.

### Unauthorized Google account

If someone signs in with Google but their email is **not** in `users` (or is inactive), login is **403**. They are not auto-registered.

### Changing a staff member’s role

1. **Users** → find the account → **Edit**.
2. Change **Role** → confirm (`Change role for email from CURRENT to NEW?`).
3. Audit records `USER_ROLE_CHANGED`.
4. On their next authenticated request / fresh login, authorization follows the new DB role.

### Deactivating an account

1. **Users** → **Edit** → **Deactivate** → confirm.
2. The user can no longer access VigilantEye (Google login denied; API rejects inactive sessions).
3. Prefer deactivation over deletion. Account deletion is not offered in the admin UI.

### Email identity

Email is the Google identity and **cannot be edited** in the admin UI. To use a different Google email, create/link the correct account.

## Administrator workspace

| Page | Purpose |
|------|---------|
| Dashboard | Live counts by role, recent user-management activity, quick actions (Add / Import / Manage / Student Directory / Roles / Security & Audit) |
| Users | Search, filter, paginate, add, edit, role change, activate/deactivate, student link |
| Import | Sample CSV download → preview → confirm → result summary → audit |
| Roles & Permissions | Informational matrix — not a permission editor |
| Audit Log | `USER_*` events (actor, action, target, details) |
| Student Directory | Read-only rolls + linked Google email + portal status (link/unlink from Users) |
| System | Non-secret env / auth / API & DB availability |
| Profile | Name, Google email, role, status, authentication method |
| Notifications | Existing notifications page |

## Bulk CSV

Columns: `email,role,name,student_roll`

Use **Download sample CSV** on the Import page. Preview shows valid, invalid, duplicates, already exists, role conflicts, and student-link problems. Existing roles are never overwritten silently. Confirm before import. Audit: `USER_BULK_IMPORTED`.

## Student linking

- Only `STUDENT` users may be linked to a student roll.
- One student ↔ one portal user; conflicts are rejected (not overwritten).
- Directory is read-only; manage links under **Users**.

## Last-admin protection

The backend refuses to demote or deactivate the **last active ADMINISTRATOR**.

## Security (authoritative on the server)

- `/admin/*` requires DB role `ADMINISTRATOR`.
- Forged JWT `role=ADMINISTRATOR` with a non-admin DB user → **403**.
- Google never assigns roles; JWT role claims never override DB role.
- Inactive administrators cannot authenticate.

## First administrator (bootstrap only)

```bash
python create_admin.py --email university-admin@gmail.com --name "University Administrator"
```

Use only for initial bootstrap — not for routine account creation.

## Production posture

```env
AUTH_MODE=google
PASSWORD_LOGIN_ENABLED=0
ENABLE_DEMO_SEED=0
```

## APIs (ADMINISTRATOR only)

Phases 18–21: users CRUD/stats/activate/deactivate, CSV preview/import, audit-logs, students directory, system-info, roles catalog.

Phase 24: `POST /admin/email/test` sends a controlled test message to the signed-in Administrator’s `User.email` only (no arbitrary recipients). System page shows safe SMTP status — never passwords. See [EMAIL_NOTIFICATIONS.md](EMAIL_NOTIFICATIONS.md).
