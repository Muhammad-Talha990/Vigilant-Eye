# Production deployment (standalone Compose — not an overlay on docker-compose.yml)
#
# Topology:
#   Browser → nginx SPA (:8080) → FastAPI (:8000) → PostgreSQL
#
# 1. Copy `.env.production.example` to `.env.production` and set real values:
#    POSTGRES_PASSWORD, JWT_SECRET (>=32 chars, not CHANGE_ME_*),
#    CORS_ORIGINS (explicit HTTPS origins, no *),
#    VITE_API_URL (browser-reachable API base URL),
#    GOOGLE_CLIENT_ID (Google OAuth Web client ID — not JWT_SECRET),
#    AUTH_MODE=google, APP_ENV=production, JWT_EXPIRE_MINUTES<=60,
#    ENABLE_API_DOCS=0, ENABLE_DEMO_SEED=0, PASSWORD_LOGIN_ENABLED=0
#
# Email (optional): set EMAIL_ENABLED=0 until SMTP is ready, or configure
# SMTP_HOST / SMTP_FROM / SMTP_USER / SMTP_PASSWORD (App Password or relay).
# Google OAuth credentials are not SMTP credentials. See docs/EMAIL_NOTIFICATIONS.md.
#
# 2. Build and start:
#    docker compose --env-file .env.production -f docker-compose.prod.yml up --build -d
#
# 3. Create authorized User rows (email + role + active). Google login only
#    succeeds for emails already in `users`. Demo seed stays off unless
#    ENABLE_DEMO_SEED=1. See docs/GOOGLE_AUTH.md.
#
# Development / viva remains:
#    docker compose up --build
#    OR  .\start-dev.ps1
#
# Demo password shortcuts appear only when Vite DEV / VITE_ENABLE_DEMO_HELPERS
# and password login are enabled. Production is Google Sign-In only.
