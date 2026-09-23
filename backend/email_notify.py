"""Optional SMTP email notifications with safe MOCK fallback."""

from __future__ import annotations

import logging
import os
import smtplib
from email.message import EmailMessage

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("vigilanteye.email")

SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "").strip()
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "").strip()
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER or "noreply@vigilanteye.local").strip()
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() in {"1", "true", "yes"}


def smtp_configured() -> bool:
    return bool(SMTP_HOST and SMTP_FROM)


def send_email(*, to_email: str, subject: str, body: str) -> str:
    """
    Send email if SMTP_* is configured; otherwise log MOCK.
    Returns 'sent' | 'mock' | 'error' — never raises to callers.
    """
    if not to_email:
        return "error"
    if not smtp_configured():
        logger.info(
            "EMAIL_MOCK to=%s subject=%s body=%s",
            to_email,
            subject,
            body[:200],
        )
        print(f"[EMAIL_MOCK] to={to_email} subject={subject}")
        return "mock"

    try:
        msg = EmailMessage()
        msg["From"] = SMTP_FROM
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.set_content(body)

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            if SMTP_USE_TLS:
                server.starttls()
            if SMTP_USER and SMTP_PASSWORD:
                server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        return "sent"
    except Exception as exc:  # noqa: BLE001
        logger.warning("EMAIL_ERROR to=%s err=%s", to_email, exc)
        print(f"[EMAIL_ERROR] to={to_email} err={exc}")
        return "error"
