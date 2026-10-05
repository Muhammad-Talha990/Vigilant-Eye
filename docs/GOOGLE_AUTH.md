# Google authentication (Phases 16–17)

## Authentication modes (`AUTH_MODE`)

| Mode | Password | Google | Demo shortcuts / seed | Allowed in production? |
|------|----------|--------|------------------------|------------------------|
| `demo` (default in development) | Yes | Hidden | Yes | **No** |
| `google` (default in production) | No | Yes (requires `GOOGLE_CLIENT_ID`) | No | **Yes** |
| `both` | Yes | Yes | Yes | **No** |

Switch development to real Google testing:

```env
AUTH_MODE=google
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
PASSWORD_LOGIN_ENABLED=0
ENABLE_DEMO_SEED=0
```

Return to viva/demo:

```env
AUTH_MODE=demo
```

Public flags: `GET /auth/config` → `auth_mode`, `password_login_enabled`, `google_auth_enabled`, `demo_helpers_enabled`, `google_client_id`.

## Flow (unchanged from Phase 16)

1. Browser GIS **Continue with Google**
2. `POST /auth/google` with `{ "id_token": "<credential>" }`
3. Backend verifies signature, issuer, audience (`GOOGLE_CLIENT_ID`), expiry, `email_verified`
4. Lookup `User` by normalized email
5. Issue portal JWT; **DB `User.role` is authoritative**

Unknown accounts → **403 Account not authorized** (no auto-create).

For university-scale authorization (ADMINISTRATOR role, CSV import, activate/deactivate), see [ADMIN_USERS.md](ADMIN_USERS.md).

## Google Cloud Console (localhost)

`GOOGLE_CLIENT_ID` is **not** the same as `JWT_SECRET`.

1. Open [Google Cloud Console](https://console.cloud.google.com/) → create/select a project.
2. **APIs & Services → OAuth consent screen** — configure External or Internal as appropriate; add test users if the app is in Testing.
3. **Credentials → Create credentials → OAuth client ID → Web application**.
4. **Authorized JavaScript origins** (GIS button; no redirect URI required for ID-token flow):
   - `http://localhost:5173`
   - `http://127.0.0.1:5173`
5. Copy the **Client ID** into `.env` as `GOOGLE_CLIENT_ID=....apps.googleusercontent.com`.
6. Restart the API container so `/auth/config` picks up the value.
7. Set `AUTH_MODE=google` and open http://localhost:5173/login.

Do **not** put `GOOGLE_CLIENT_SECRET` in the SPA. This project verifies GIS ID tokens with the client ID only.

## Provisioning authorized accounts

Domain membership alone does **not** grant access. Create explicit `User` rows:

```powershell
cd backend
python provision_test_google_users.py --email 232514@students.au.edu.pk --role STUDENT --student-roll 232514
python provision_test_google_users.py --email staff.example@gmail.com --role HOD --name "HOD Tester"
```

Or use User Management in the portal (HOD / Exam Department) while still in `AUTH_MODE=demo` or `both`, then switch to `google`.

## Email notifications

Portal notifications always use `Notification.user_id`. Optional SMTP via `EMAIL_ENABLED` / `SMTP_*`. Failures never roll back case updates. If SMTP is unset, expect MOCK logs only. Google Sign-In is **not** the SMTP transport — see [EMAIL_NOTIFICATIONS.md](EMAIL_NOTIFICATIONS.md).
