"""Google Identity (OIDC ID token) verification for institutional login."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from app_config import GOOGLE_CLIENT_ID, google_auth_enabled


ALLOWED_ISSUERS = frozenset(
    {
        "accounts.google.com",
        "https://accounts.google.com",
    }
)


@dataclass(frozen=True)
class GoogleIdentity:
    email: str
    email_verified: bool
    subject: str
    name: str | None


def normalize_email(email: str) -> str:
    """Exact match key: trim + lowercase. No alias rewriting."""
    return (email or "").strip().lower()


def verify_google_id_token(credential: str) -> GoogleIdentity:
    """
    Verify a Google Sign-In / GIS ID token.

    Checks signature, expiry, audience (GOOGLE_CLIENT_ID), and issuer.
    Raises HTTPException on any validation failure.
    """
    if not google_auth_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google authentication is not configured",
        )
    token = (credential or "").strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Google credential",
        )

    try:
        claims = id_token.verify_oauth2_token(
            token,
            google_requests.Request(),
            GOOGLE_CLIENT_ID,
            clock_skew_in_seconds=10,
        )
    except ValueError as exc:
        # google-auth raises ValueError for bad sig, aud, exp, iss, etc.
        message = str(exc).lower()
        if "expired" in message:
            detail = "Google credential expired"
        elif "audience" in message:
            detail = "Google credential audience mismatch"
        elif "issuer" in message:
            detail = "Google credential issuer mismatch"
        else:
            detail = "Invalid Google credential"
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google credential",
        ) from exc

    issuer = str(claims.get("iss") or "")
    if issuer not in ALLOWED_ISSUERS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google credential issuer mismatch",
        )

    email = normalize_email(str(claims.get("email") or ""))
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google credential missing email",
        )

    email_verified = bool(claims.get("email_verified"))
    if not email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Google email is not verified",
        )

    return GoogleIdentity(
        email=email,
        email_verified=email_verified,
        subject=str(claims.get("sub") or ""),
        name=(str(claims["name"]) if claims.get("name") else None),
    )
