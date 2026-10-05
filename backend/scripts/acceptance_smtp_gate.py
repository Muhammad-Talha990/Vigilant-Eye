"""Acceptance gate: real SMTP + failure handling. Never prints secrets."""

from __future__ import annotations

import os
import sys

# Ensure backend imports resolve when run from /app/backend
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from email_notify import (  # noqa: E402
    get_email_status,
    mask_email,
    reload_email_config_from_env,
    send_email,
    smtp_configured,
)


def main() -> int:
    reload_email_config_from_env()
    status0 = get_email_status()
    print("smtp_configured=", smtp_configured())
    print("email_notifications=", status0.get("email_notifications"))
    print("smtp_host=", status0.get("smtp_host"))
    print("smtp_auth_configured=", status0.get("smtp_auth_configured"))
    print("from_configured=", status0.get("smtp_from_configured"))

    to = os.environ.get("SMTP_FROM") or os.environ.get("SMTP_USER")
    if not to:
        print("NO_RECIPIENT")
        return 2
    print("to_masked=", mask_email(to))

    result = send_email(
        to_email=to,
        subject="VigilantEye: Acceptance SMTP self-test",
        body=(
            "Automated VigilantEye acceptance-gate SMTP self-test.\n"
            "If received, SMTP auth and server acceptance succeeded.\n"
            "Portal: " + (os.environ.get("PORTAL_BASE_URL") or "(unset)")
        ),
        html=(
            "<p>VigilantEye acceptance SMTP self-test. "
            "Portal notifications remain the primary channel.</p>"
        ),
    )
    print("send_result=", result)
    st = get_email_status()
    print("last_status=", st.get("last_delivery_status"))
    print("last_error=", st.get("last_delivery_error_category"))
    print("last_to=", st.get("last_delivery_to_masked"))
    pwd = os.environ.get("SMTP_PASSWORD") or ""
    if pwd and pwd in str(st):
        print("SECRET_LEAK_IN_STATUS")
        return 3

    # Failure handling in this process only (does not mutate container env permanently)
    saved_host = os.environ.get("SMTP_HOST", "")
    os.environ["SMTP_HOST"] = "smtp.invalid.vigilanteye.test"
    reload_email_config_from_env()
    bad = send_email(to_email=to, subject="fail-host", body="x")
    print("bad_host_result=", bad)
    st2 = get_email_status()
    print("bad_host_category=", st2.get("last_delivery_error_category"))
    if bad != "error":
        print("BAD_HOST_EXPECTED_ERROR")
        return 4
    if pwd and pwd in str(st2):
        print("SECRET_LEAK_ON_ERROR")
        return 5

    # Restore for cleanliness if anything else imports this process
    os.environ["SMTP_HOST"] = saved_host
    reload_email_config_from_env()
    print("FAILURE_HANDLING_OK")
    return 0 if result == "sent" else 10


if __name__ == "__main__":
    raise SystemExit(main())
