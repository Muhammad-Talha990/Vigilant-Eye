"""
Runtime configuration for VigilantEye API (environment-driven).

APP_ENV=development|production (default: development)
AUTH_MODE=demo|google|both (default: demo in development, google in production)
"""

from __future__ import annotations

import os
import re

from dotenv import load_dotenv

load_dotenv()

APP_ENV = (os.getenv("APP_ENV") or "development").strip().lower()
IS_PRODUCTION = APP_ENV in {"production", "prod"}

# Docs: enabled in non-production unless explicitly disabled; disabled in production
# unless ENABLE_API_DOCS=1.
_docs_env = (os.getenv("ENABLE_API_DOCS") or "").strip().lower()
if _docs_env in {"1", "true", "yes", "on"}:
    ENABLE_API_DOCS = True
elif _docs_env in {"0", "false", "no", "off"}:
    ENABLE_API_DOCS = False
else:
    ENABLE_API_DOCS = not IS_PRODUCTION

# Google Identity (OIDC ID token). Client ID is public; secret unused for GIS ID tokens.
GOOGLE_CLIENT_ID = (os.getenv("GOOGLE_CLIENT_ID") or "").strip()
# Optional — reserved for authorization-code / server flows; not required for GIS.
GOOGLE_CLIENT_SECRET = (os.getenv("GOOGLE_CLIENT_SECRET") or "").strip()
GOOGLE_REDIRECT_URI = (os.getenv("GOOGLE_REDIRECT_URI") or "").strip()

ALLOWED_AUTH_MODES = frozenset({"demo", "google", "both"})

# Comma-separated browser origins. Empty → localhost Vite defaults (dev-safe).
_DEFAULT_CORS = (
    "http://localhost:5173,"
    "http://127.0.0.1:5173,"
    "http://localhost:3000,"
    "http://127.0.0.1:3000"
)

_PLACEHOLDER_RE = re.compile(
    r"(CHANGE_ME|changeme|replace_me|your[_-]?secret|audit-placeholder)",
    re.IGNORECASE,
)


def _env_flag(name: str) -> str:
    return (os.getenv(name) or "").strip().lower()


def _flag_explicit(name: str) -> bool | None:
    flag = _env_flag(name)
    if flag in {"1", "true", "yes", "on"}:
        return True
    if flag in {"0", "false", "no", "off"}:
        return False
    return None


def _looks_like_placeholder(value: str) -> bool:
    return bool(value and _PLACEHOLDER_RE.search(value))


def auth_mode() -> str:
    """
    Authentication mode:

    - demo: password + viva shortcuts; Google hidden
    - google: Google only; no password/demo shortcuts/seed
    - both: Google + password/demo (development only)

    Unset → production: google; development: demo.
    """
    raw = (os.getenv("AUTH_MODE") or "").strip().lower()
    if IS_PRODUCTION:
        if raw in {"demo", "both"}:
            return raw  # validate_production_settings will reject
        return "google" if raw in {"", "google"} else raw
    if raw in ALLOWED_AUTH_MODES:
        return raw
    return "demo"


def google_client_configured() -> bool:
    """True when a non-placeholder Google OAuth client ID is set."""
    if not GOOGLE_CLIENT_ID:
        return False
    if _looks_like_placeholder(GOOGLE_CLIENT_ID):
        return False
    return True


def google_auth_enabled() -> bool:
    """Google Sign-In offered when client ID is set and AUTH_MODE allows it."""
    mode = auth_mode()
    if mode == "demo":
        return False
    if mode not in {"google", "both"}:
        return False
    return google_client_configured()


def password_login_enabled() -> bool:
    """
    Password login for development/viva.

    AUTH_MODE drives defaults; PASSWORD_LOGIN_ENABLED=0|1 overrides.
    """
    flag = _flag_explicit("PASSWORD_LOGIN_ENABLED")
    if flag is not None:
        return flag
    mode = auth_mode()
    if mode == "google":
        return False
    if mode in {"demo", "both"}:
        return True
    return not IS_PRODUCTION


def demo_helpers_enabled() -> bool:
    """
    Evaluation shortcuts / demo monitoring affordances.

    Off in AUTH_MODE=google and always off in production.
    """
    if IS_PRODUCTION:
        return False
    mode = auth_mode()
    return mode in {"demo", "both"}


def demo_seed_enabled() -> bool:
    """
    Whether bootstrap may create *@demo.com users / demo cameras.

    - ENABLE_DEMO_SEED=1|0 → explicit
    - AUTH_MODE=google → off unless ENABLE_DEMO_SEED=1
    - unset → allow only when not production and not google-only mode
    """
    flag = _flag_explicit("ENABLE_DEMO_SEED")
    if flag is not None:
        return flag
    if auth_mode() == "google":
        return False
    return not IS_PRODUCTION


def cors_allow_origins() -> list[str]:
    raw = (os.getenv("CORS_ORIGINS") or "").strip()
    if not raw:
        if IS_PRODUCTION:
            raise RuntimeError(
                "CORS_ORIGINS is required when APP_ENV=production "
                "(comma-separated HTTPS origins; wildcard * is not allowed)"
            )
        return [o.strip() for o in _DEFAULT_CORS.split(",") if o.strip()]
    origins = [o.strip() for o in raw.split(",") if o.strip()]
    if IS_PRODUCTION and any(o == "*" for o in origins):
        raise RuntimeError(
            "CORS_ORIGINS must not use wildcard '*' in production"
        )
    return origins


def validate_production_settings() -> None:
    """
    Fail fast on unsafe production configuration.
    No-op when APP_ENV is not production.
    """
    if not IS_PRODUCTION:
        return

    errors: list[str] = []

    secret = (os.getenv("JWT_SECRET") or "").strip()
    if not secret:
        errors.append("JWT_SECRET is required in production")
    elif len(secret) < 32:
        errors.append("JWT_SECRET must be at least 32 characters in production")
    elif _looks_like_placeholder(secret):
        errors.append(
            "JWT_SECRET must not be an example/placeholder value in production"
        )

    try:
        jwt_minutes = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))
    except ValueError:
        errors.append("JWT_EXPIRE_MINUTES must be an integer")
        jwt_minutes = 60
    if jwt_minutes < 1:
        errors.append("JWT_EXPIRE_MINUTES must be >= 1")
    elif jwt_minutes > 60:
        errors.append(
            "JWT_EXPIRE_MINUTES must be <= 60 in production "
            f"(got {jwt_minutes})"
        )

    cors_raw = (os.getenv("CORS_ORIGINS") or "").strip()
    if not cors_raw:
        errors.append("CORS_ORIGINS is required in production")
    elif "*" in [o.strip() for o in cors_raw.split(",")]:
        errors.append("CORS_ORIGINS must not use wildcard '*' in production")

    # Reject example DB passwords whether set via POSTGRES_PASSWORD or URL.
    pg_password = (os.getenv("POSTGRES_PASSWORD") or "").strip()
    database_url = (os.getenv("DATABASE_URL") or "").strip()
    if pg_password and _looks_like_placeholder(pg_password):
        errors.append(
            "POSTGRES_PASSWORD must not be an example/placeholder value "
            "in production"
        )
    if database_url and _looks_like_placeholder(database_url):
        errors.append(
            "DATABASE_URL must not contain example/placeholder credentials "
            "in production"
        )
    if not pg_password and not database_url:
        errors.append(
            "DATABASE_URL or POSTGRES_PASSWORD must be set in production"
        )

    mode = auth_mode()
    if mode != "google":
        errors.append(
            f"AUTH_MODE must be 'google' in production (got '{mode}'; "
            "demo/both are not allowed)"
        )

    if not google_client_configured():
        errors.append(
            "GOOGLE_CLIENT_ID is required in production "
            "(non-placeholder OAuth client ID)"
        )

    if password_login_enabled():
        errors.append(
            "PASSWORD_LOGIN_ENABLED must be off in production "
            "(set PASSWORD_LOGIN_ENABLED=0 or leave unset with AUTH_MODE=google)"
        )

    if demo_seed_enabled():
        errors.append(
            "ENABLE_DEMO_SEED must be off in production"
        )

    # Email: allow EMAIL_ENABLED=0 without SMTP; if email is on, SMTP must be usable.
    try:
        from email_notify import validate_email_settings_for_production

        errors.extend(validate_email_settings_for_production())
    except Exception as exc:  # noqa: BLE001
        errors.append(f"email configuration validation failed: {type(exc).__name__}")

    if errors:
        joined = "\n  - ".join(errors)
        raise RuntimeError(
            "Unsafe production configuration (APP_ENV=production):\n"
            f"  - {joined}"
        )
