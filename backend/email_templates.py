"""Safe HTML + plain-text email bodies for VigilantEye notifications."""

from __future__ import annotations

import html
from dataclasses import dataclass


APP_NAME = "VigilantEye"


@dataclass(frozen=True)
class EmailContent:
    subject: str
    text: str
    html: str


def _portal_url(portal_base_url: str | None) -> str | None:
    base = (portal_base_url or "").strip().rstrip("/")
    return base or None


def build_notification_email(
    *,
    title: str,
    message: str,
    case_id: int | None = None,
    notification_type: str | None = None,
    portal_base_url: str | None = None,
) -> EmailContent:
    """
    Build escaped HTML + plain-text content.

    Prefer directing the recipient to the portal rather than embedding
    confidential case evidence in email.
    """
    safe_title = (title or "Notification").strip() or "Notification"
    safe_message = (message or "").strip()
    # Cap body length to avoid dumping large confidential text into email.
    if len(safe_message) > 500:
        safe_message = safe_message[:497] + "..."

    subject = f"{APP_NAME}: {safe_title}"

    portal = _portal_url(portal_base_url)
    lines = [
        f"{APP_NAME} notification",
        "",
        safe_title,
        "",
        safe_message or "An update is available in the portal.",
        "",
    ]
    if case_id is not None:
        lines.append(f"Related case reference: #{case_id}")
        lines.append("")
    if notification_type:
        lines.append(f"Event type: {notification_type}")
        lines.append("")
    if portal:
        lines.append(f"Open the portal: {portal}")
        lines.append("")
    lines.append(
        "This message does not include confidential evidence. "
        "Sign in to the portal for details."
    )
    lines.append("")
    lines.append(f"— {APP_NAME}")
    text = "\n".join(lines)

    esc_title = html.escape(safe_title)
    esc_message = html.escape(
        safe_message or "An update is available in the portal."
    )
    esc_app = html.escape(APP_NAME)
    case_html = (
        f"<p style=\"margin:0 0 12px;color:#334155;font-size:14px;\">"
        f"Related case reference: <strong>#{int(case_id)}</strong></p>"
        if case_id is not None
        else ""
    )
    type_html = (
        f"<p style=\"margin:0 0 12px;color:#64748b;font-size:13px;\">"
        f"Event type: {html.escape(notification_type)}</p>"
        if notification_type
        else ""
    )
    if portal:
        esc_portal = html.escape(portal)
        cta = (
            f'<p style="margin:20px 0 8px;">'
            f'<a href="{esc_portal}" style="display:inline-block;padding:10px 16px;'
            f"background:#0f2744;color:#ffffff;text-decoration:none;"
            f'border-radius:6px;font-size:14px;">Open {esc_app} portal</a></p>'
            f'<p style="margin:0;color:#64748b;font-size:12px;">{esc_portal}</p>'
        )
    else:
        cta = (
            "<p style=\"margin:16px 0 0;color:#64748b;font-size:13px;\">"
            "Sign in to the VigilantEye portal for details.</p>"
        )

    html_body = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>{esc_app}</title></head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:Segoe UI,Helvetica,Arial,sans-serif;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f1f5f9;padding:24px 12px;">
    <tr><td align="center">
      <table role="presentation" width="560" cellspacing="0" cellpadding="0" style="background:#ffffff;border:1px solid #e2e8f0;border-radius:8px;padding:28px 24px;">
        <tr><td>
          <p style="margin:0 0 4px;font-size:12px;letter-spacing:0.06em;text-transform:uppercase;color:#64748b;">{esc_app}</p>
          <h1 style="margin:0 0 16px;font-size:20px;line-height:1.3;color:#0f2744;">{esc_title}</h1>
          <p style="margin:0 0 12px;font-size:15px;line-height:1.5;color:#1e293b;">{esc_message}</p>
          {case_html}
          {type_html}
          {cta}
          <p style="margin:24px 0 0;font-size:12px;line-height:1.4;color:#94a3b8;">
            This message does not include confidential evidence. Sign in to the portal for details.
          </p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>
"""
    return EmailContent(subject=subject, text=text, html=html_body)


def build_test_email(*, portal_base_url: str | None = None) -> EmailContent:
    return build_notification_email(
        title="Administrator test email",
        message=(
            "This is a controlled test message from VigilantEye. "
            "If you received this, SMTP delivery is working for your account."
        ),
        notification_type="ADMIN_EMAIL_TEST",
        portal_base_url=portal_base_url,
    )
