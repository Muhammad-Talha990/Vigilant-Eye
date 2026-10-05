"""Optional SMTP email notifications with safe MOCK / disable modes.

Google authentication answers "who is this user?"
SMTP answers "how does VigilantEye send an email notification?"
They are separate; Google OAuth credentials must never be used as SMTP secrets.
"""

from __future__ import annotations

import logging
import os
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import formataddr
from typing import Any

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("vigilanteye.email")

# EMAIL_ENABLED: unset → send when SMTP configured (or MOCK); 0 → skip entirely.
_email_flag = (os.getenv("EMAIL_ENABLED") or "").strip().lower()
if _email_flag in {"0", "false", "no", "off"}:
    EMAIL_ENABLED = False
elif _email_flag in {"1", "true", "yes", "on"}:
    EMAIL_ENABLED = True
else:
    EMAIL_ENABLED = True  # default on; MOCK when SMTP missing

SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "587") or "587")
# Prefer SMTP_USER; accept SMTP_USERNAME as documented alias.
SMTP_USER = (
    os.getenv("SMTP_USER") or os.getenv("SMTP_USERNAME") or ""
).strip()
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "").strip()
# Prefer SMTP_FROM; accept SMTP_FROM_EMAIL alias.
SMTP_FROM = (
    os.getenv("SMTP_FROM")
    or os.getenv("SMTP_FROM_EMAIL")
    or SMTP_USER
    or "noreply@vigilanteye.local"
).strip()
SMTP_FROM_NAME = (os.getenv("SMTP_FROM_NAME") or "VigilantEye").strip()
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() in {"1", "true", "yes"}
try:
    SMTP_TIMEOUT_SECONDS = max(1, int(os.getenv("SMTP_TIMEOUT_SECONDS", "15") or "15"))
except ValueError:
    SMTP_TIMEOUT_SECONDS = 15

PORTAL_BASE_URL = (os.getenv("PORTAL_BASE_URL") or "").strip().rstrip("/")

# Process-level last delivery status (safe fields only; never stores secrets/body).
_LAST_DELIVERY: dict[str, Any] = {
    "status": "never",  # never | sent | mock | disabled | error
    "at": None,
    "to_masked": None,
    "subject_preview": None,
    "error_category": None,
}


def mask_email(addr: str | None) -> str:
    """Mask a recipient for logs / admin UI (never log full mailbox unnecessarily)."""
    if not addr or "@" not in addr:
        return "***"
    local, domain = addr.rsplit("@", 1)
    if not local:
        return f"***@{domain}"
    return f"{local[0]}***@{domain}"


def smtp_configured() -> bool:
    """True when enough SMTP settings exist to attempt a real send."""
    return bool(SMTP_HOST and SMTP_FROM)


def email_enabled_explicitly() -> bool:
    """True when EMAIL_ENABLED was set on (1/true/yes/on)."""
    flag = (os.getenv("EMAIL_ENABLED") or "").strip().lower()
    return flag in {"1", "true", "yes", "on"}


def reload_email_config_from_env() -> None:
    """Refresh module config from environment (tests / rare runtime reload)."""
    global EMAIL_ENABLED, SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD
    global SMTP_FROM, SMTP_FROM_NAME, SMTP_USE_TLS, SMTP_TIMEOUT_SECONDS
    global PORTAL_BASE_URL

    flag = (os.getenv("EMAIL_ENABLED") or "").strip().lower()
    if flag in {"0", "false", "no", "off"}:
        EMAIL_ENABLED = False
    elif flag in {"1", "true", "yes", "on"}:
        EMAIL_ENABLED = True
    else:
        EMAIL_ENABLED = True

    SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
    try:
        SMTP_PORT = int(os.getenv("SMTP_PORT", "587") or "587")
    except ValueError:
        SMTP_PORT = 587
    SMTP_USER = (os.getenv("SMTP_USER") or os.getenv("SMTP_USERNAME") or "").strip()
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "").strip()
    SMTP_FROM = (
        os.getenv("SMTP_FROM")
        or os.getenv("SMTP_FROM_EMAIL")
        or SMTP_USER
        or "noreply@vigilanteye.local"
    ).strip()
    SMTP_FROM_NAME = (os.getenv("SMTP_FROM_NAME") or "VigilantEye").strip()
    SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() in {"1", "true", "yes"}
    try:
        SMTP_TIMEOUT_SECONDS = max(
            1, int(os.getenv("SMTP_TIMEOUT_SECONDS", "15") or "15")
        )
    except ValueError:
        SMTP_TIMEOUT_SECONDS = 15
    PORTAL_BASE_URL = (os.getenv("PORTAL_BASE_URL") or "").strip().rstrip("/")


def _record_delivery(
    *,
    status: str,
    to_email: str | None = None,
    subject: str | None = None,
    error_category: str | None = None,
) -> None:
    _LAST_DELIVERY["status"] = status
    _LAST_DELIVERY["at"] = datetime.now(timezone.utc).isoformat()
    _LAST_DELIVERY["to_masked"] = mask_email(to_email) if to_email else None
    preview = (subject or "")[:80] or None
    _LAST_DELIVERY["subject_preview"] = preview
    _LAST_DELIVERY["error_category"] = error_category


def get_email_status() -> dict[str, Any]:
    """
    Safe email configuration + last-delivery summary for Administrator System page.
    Never includes passwords, tokens, or message bodies.
    """
    configured = smtp_configured()
    if not EMAIL_ENABLED:
        notifications = "disabled"
    elif configured:
        notifications = "enabled"
    else:
        notifications = "mock"  # enabled but SMTP incomplete → MOCK mode

    provider = SMTP_HOST if configured else None
    last = dict(_LAST_DELIVERY)
    return {
        "email_notifications": notifications,
        "email_enabled": bool(EMAIL_ENABLED),
        "smtp_configured": configured,
        "smtp_host": provider,
        "smtp_port": SMTP_PORT if configured else None,
        "smtp_use_tls": SMTP_USE_TLS if configured else None,
        "smtp_from_configured": bool(SMTP_FROM) if configured else False,
        "smtp_auth_configured": bool(SMTP_USER and SMTP_PASSWORD),
        "portal_base_url_configured": bool(PORTAL_BASE_URL),
        "last_delivery_status": last.get("status") or "never",
        "last_delivery_at": last.get("at"),
        "last_delivery_to_masked": last.get("to_masked"),
        "last_delivery_error_category": last.get("error_category"),
    }


def validate_email_settings_for_production() -> list[str]:
    """
    Return production misconfiguration messages when email is explicitly enabled.
    Empty list means OK (or email disabled / default MOCK-friendly unset).

    Per Phase 24: do not require SMTP merely to boot; but if EMAIL_ENABLED=1,
    SMTP must be usable.
    """
    errors: list[str] = []
    flag = (os.getenv("EMAIL_ENABLED") or "").strip().lower()
    # Only enforce when operators explicitly enable email.
    if flag not in {"1", "true", "yes", "on"}:
        return errors
    if not (os.getenv("SMTP_HOST") or "").strip():
        errors.append(
            "EMAIL_ENABLED=1 requires SMTP_HOST in production "
            "(or set EMAIL_ENABLED=0 to disable email)"
        )
    from_addr = (
        os.getenv("SMTP_FROM") or os.getenv("SMTP_FROM_EMAIL") or ""
    ).strip()
    if not from_addr:
        errors.append(
            "EMAIL_ENABLED=1 requires SMTP_FROM or SMTP_FROM_EMAIL in production"
        )
    user = (os.getenv("SMTP_USER") or os.getenv("SMTP_USERNAME") or "").strip()
    password = (os.getenv("SMTP_PASSWORD") or "").strip()
    if user and not password:
        errors.append(
            "SMTP_USER/SMTP_USERNAME is set but SMTP_PASSWORD is empty "
            "(Gmail/Workspace usually requires an App Password)"
        )
    return errors


def send_email(
    *,
    to_email: str,
    subject: str,
    body: str,
    html: str | None = None,
) -> str:
    """
    Send email if enabled and SMTP_* is configured; otherwise MOCK or skip.

    Returns 'sent' | 'mock' | 'disabled' | 'error' — never raises to callers.
    Never logs SMTP passwords, tokens, or full message bodies.
    """
    if not to_email:
        _record_delivery(status="error", error_category="missing_recipient")
        return "error"
    masked = mask_email(to_email)
    if not EMAIL_ENABLED:
        logger.info("EMAIL_DISABLED to=%s subject=%s", masked, (subject or "")[:80])
        _record_delivery(
            status="disabled", to_email=to_email, subject=subject
        )
        return "disabled"
    if not smtp_configured():
        logger.info(
            "EMAIL_MOCK to=%s subject=%s",
            masked,
            (subject or "")[:80],
        )
        print(f"[EMAIL_MOCK] to={masked} subject={(subject or '')[:80]}")
        _record_delivery(status="mock", to_email=to_email, subject=subject)
        return "mock"

    try:
        msg = EmailMessage()
        if SMTP_FROM_NAME:
            msg["From"] = formataddr((SMTP_FROM_NAME, SMTP_FROM))
        else:
            msg["From"] = SMTP_FROM
        msg["To"] = to_email
        msg["Subject"] = subject or ""
        msg.set_content(body or "")
        if html:
            msg.add_alternative(html, subtype="html")

        with smtplib.SMTP(
            SMTP_HOST, SMTP_PORT, timeout=SMTP_TIMEOUT_SECONDS
        ) as server:
            if SMTP_USE_TLS:
                server.starttls()
            if SMTP_USER and SMTP_PASSWORD:
                server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        logger.info("EMAIL_SENT to=%s subject=%s", masked, (subject or "")[:80])
        _record_delivery(status="sent", to_email=to_email, subject=subject)
        return "sent"
    except Exception as exc:  # noqa: BLE001
        category = type(exc).__name__
        logger.warning("EMAIL_ERROR to=%s err=%s", masked, category)
        print(f"[EMAIL_ERROR] to={masked} err={category}")
        _record_delivery(
            status="error",
            to_email=to_email,
            subject=subject,
            error_category=category,
        )
        return "error"
