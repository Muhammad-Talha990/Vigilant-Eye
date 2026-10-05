# VigilantEye — Email notifications (Phase 24)

## 1. Architecture

Portal notifications and email notifications are related but separate:

```
Workflow event
  → create_notification(user_id, …)     # always persists Notification row
  → DB commit
  → (after_commit) email service
       → load User by Notification.user_id
       → recipient = User.email only
       → SMTP or EMAIL_MOCK / disabled
```

- **Portal notification**: always created for the target `user_id`.
- **Email notification**: only for allowlisted important types, and only after a successful DB commit.
- SMTP failures are logged safely and **never** roll back case / notification DB work.
- Sending is **synchronous with a bounded timeout** (`SMTP_TIMEOUT_SECONDS`, default 15s). No Redis/Celery queue in this phase.

## 2. Google authentication vs SMTP

| Concern | System |
|--------|--------|
| Who is this user? | Google Sign-In → JWT session; DB `User.email` / `User.role` |
| How do we send mail? | SMTP (`SMTP_*` env) |

- Do **not** use `GOOGLE_CLIENT_ID` or Google client secret as an SMTP password.
- The Google login account does **not** automatically become the SMTP sender.
- Universities typically use a dedicated mailbox (e.g. `notifications@…`) configured via `SMTP_FROM` / `SMTP_FROM_EMAIL`.

## 3. Authoritative recipient

Recipient is always **`User.email`** for the notification’s `user_id`.

The system does **not**:

- take recipient addresses from the frontend
- invent student/staff emails from roles or domains
- email inactive users for new workflow events
- use Google token claims after login as the mail target

Administrator **Send Test Email** always sends to the authenticated Administrator’s own `User.email`.

## 4. Environment variables (names only)

| Variable | Purpose |
|----------|---------|
| `EMAIL_ENABLED` | `0` disables all sends; unset/`1` enables (MOCK if SMTP incomplete) |
| `SMTP_HOST` | SMTP server hostname |
| `SMTP_PORT` | Port (default `587`) |
| `SMTP_USER` | SMTP auth username |
| `SMTP_USERNAME` | Alias for `SMTP_USER` |
| `SMTP_PASSWORD` | SMTP auth secret (App Password / relay secret — never commit) |
| `SMTP_FROM` | Envelope/from address |
| `SMTP_FROM_EMAIL` | Alias for `SMTP_FROM` |
| `SMTP_FROM_NAME` | Display name (default `VigilantEye`) |
| `SMTP_USE_TLS` | STARTTLS (default true) |
| `SMTP_TIMEOUT_SECONDS` | SMTP socket timeout (default `15`) |
| `PORTAL_BASE_URL` | Public portal URL for email links (no tokens) |

Frontend never receives SMTP credentials (Compose/API only).

## 5. Gmail / Google Workspace

- Do **not** store the normal Google account password as `SMTP_PASSWORD`.
- Prefer a Google **App Password** (if allowed by Workspace policy) or an **approved SMTP relay**.
- Workspace admins may require IP allowlists or relay-only sending.
- Sender address should match university policy (`SMTP_FROM`).

## 6. Notification matrix

| Event / type | Portal | Email | Recipient |
|--------------|--------|-------|-----------|
| `CASE_CREATED` | Yes | Yes | Target `User.email` |
| `CASE_STATUS` | Yes | Yes | Target `User.email` |
| `CASE_ACTION_REQUIRED` | Yes | Yes | Target `User.email` |
| `CASE_DRAFT` (and other `CASE_*`) | Yes | Yes | Target `User.email` |
| `CLARIFICATION` | Yes | Yes | Target `User.email` |
| `CLARIFICATION_SUBMITTED` | Yes | Yes | Target `User.email` |
| `RESULT_HOLD` | Yes | Yes | Target `User.email` |
| `RESULT_RELEASED` | Yes | Yes | Target `User.email` |
| `DETECTION_ALERT` | Yes | Yes | Target `User.email` |
| Other portal-only types | Yes | No | — |
| Inactive user (any type) | Yes | No | — |
| `send_mail=False` | Yes | No | — |

## 7. Templates

`email_templates.py` builds:

- subject (`VigilantEye: …`)
- plain-text body
- HTML body (HTML-escaped user/title/message text)

Emails direct the user to the portal and avoid embedding evidence, JWTs, passwords, or private URLs.

## 8. Administrator test procedure

1. Sign in as ADMINISTRATOR (Google).
2. Open **Administration → System**.
3. Review safe email status (enabled/disabled, SMTP configured, last delivery).
4. Click **Send Test Email**.
5. Message is sent only to your `User.email`.
6. Confirm mailbox (if real SMTP) or `EMAIL_MOCK` / error result in UI.

API: `POST /admin/email/test` (ADMINISTRATOR only).

## 9. Failure behavior

| Failure | Portal notification | DB workflow | API |
|---------|---------------------|-------------|-----|
| SMTP down / timeout | Kept | Committed | Succeeds; email status `error` |
| `EMAIL_ENABLED=0` | Kept | Committed | Email `disabled` |
| Incomplete SMTP | Kept | Committed | `EMAIL_MOCK` |
| Rollback before commit | Not committed | Rolled back | No email sent |

## 10. Logging

Logs may include: event outcome, masked recipient, subject preview, error category, timestamp.

Logs must **not** include: SMTP password, JWT, Google secrets, DB passwords, full confidential UFM bodies.

## 11. Production recommendations

- Production boot validates: if `EMAIL_ENABLED=1` (explicit), `SMTP_HOST` and from-address are required. Unset `EMAIL_ENABLED` still allows boot (MOCK when SMTP incomplete); set `EMAIL_ENABLED=0` to disable.
- Use `PORTAL_BASE_URL` with the public HTTPS portal URL.
- Prefer a dedicated notifications mailbox and App Password / relay.
- Use Administrator test email before go-live; do not mass-email real students during dry runs.

## 12. Current limitations

- Synchronous SMTP (bounded timeout); no background worker queue.
- Last-delivery status is process-local (resets on API restart).
- No automatic multi-attempt retry beyond a single SMTP connection attempt.
- Real mailbox delivery requires university SMTP credentials (not shipped in repo).

## Troubleshooting

| Symptom | Check |
|---------|--------|
| Always `EMAIL_MOCK` | `SMTP_HOST` / `SMTP_FROM` empty |
| `EMAIL_DISABLED` | `EMAIL_ENABLED=0` |
| Auth errors | App Password / relay; not Google OAuth client secret |
| No email but portal OK | Expected when SMTP fails — check logs for `EMAIL_ERROR` category |
| Wrong recipient | Fix `User.email` in Administrator user management |
