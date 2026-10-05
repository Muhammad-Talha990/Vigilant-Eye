"""
C30 — VigilantEye timestamp contract.

Architecture
------------
- **Storage:** naive UTC in PostgreSQL ``TIMESTAMP WITHOUT TIME ZONE``.
  Historical and live data (API container TZ=UTC + ``utcnow`` / UTC now)
  are treated as UTC wall-clock values. No silent rewrite of history.
- **API JSON:** ISO-8601 with explicit UTC marker ``Z``
  (e.g. ``2026-10-04T10:18:31.123456Z``).
- **CSV export:** same UTC ISO-8601 with ``Z`` (machine-readable).
- **UI display:** frontend converts UTC → ``Asia/Karachi`` (UTC+05:00).

Do not store Pakistan local time as if it were UTC.
"""

from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Authoritative server UTC instant as naive datetime (DB/API contract)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_api_iso(value: datetime | None) -> str | None:
    """Serialize a datetime as unambiguous UTC ISO-8601 (…Z)."""
    if value is None:
        return None
    if not isinstance(value, datetime):
        raise TypeError(f"expected datetime, got {type(value)!r}")
    dt = value
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    # Naive values are UTC by project contract.
    text = dt.isoformat(sep="T")
    if text.endswith("Z") or text.endswith("z"):
        return text
    # Reject accidental offset-naive mishaps that already include an offset char
    if len(text) >= 6 and (text[-6] in "+-" or text.endswith("+00:00")):
        return text.replace("+00:00", "Z")
    return text + "Z"
