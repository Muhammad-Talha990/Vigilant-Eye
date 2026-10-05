"""
Thin alias for portal email sending (Phase 16 / Phase 24).

Canonical implementation: email_notify.send_email
"""

from email_notify import (
    EMAIL_ENABLED,
    get_email_status,
    mask_email,
    send_email,
    smtp_configured,
)

__all__ = [
    "EMAIL_ENABLED",
    "get_email_status",
    "mask_email",
    "send_email",
    "smtp_configured",
]
