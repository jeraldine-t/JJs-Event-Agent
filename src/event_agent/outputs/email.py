from __future__ import annotations

import html
import logging
import smtplib
import ssl
from datetime import datetime
from email.message import EmailMessage

from event_agent.config import Settings
from event_agent.models import Event
from event_agent.outputs.dashboard import _event_row

LOGGER = logging.getLogger(__name__)
MAX_EMAIL_EVENTS = 25


def _build_text(events: list[Event], generated_at: datetime) -> str:
    lines = [
        f"JJs Event Agent found {len(events)} upcoming Singapore event(s).",
        f"Updated {generated_at:%d %b %Y, %-I:%M %p} SGT.",
        "",
    ]
    if not events:
        lines.append("No events matched the current topic, location, date, and timing filters.")
        return "\n".join(lines)

    for event in events[:MAX_EMAIL_EVENTS]:
        row = _event_row(event)
        lines.extend(
            [
                str(row["title"]),
                f"When: {row['date_label']} at {row['time_label']}",
                f"Where: {row['location']}",
                f"F&B: {row['fnb_label']}",
                f"Interest: {row['popularity_label'] or 'Not available'}",
                f"Source: {row['source']}",
                f"Summary: {row['summary']}",
                f"Register: {row['url']}",
                "",
            ]
        )
    if len(events) > MAX_EMAIL_EVENTS:
        lines.append(f"Plus {len(events) - MAX_EMAIL_EVENTS} more event(s) in the dashboard.")
    return "\n".join(lines)


def _build_html(events: list[Event], generated_at: datetime) -> str:
    cards: list[str] = []
    for event in events[:MAX_EMAIL_EVENTS]:
        row = _event_row(event)
        popularity = html.escape(str(row["popularity_label"] or "Not available"))
        hot_pick = "<strong>Hot pick · </strong>" if row["hot_pick"] else ""
        cards.append(
            "<article style=\"margin:0 0 16px;padding:16px;border:1px solid #d9e2ea;"
            "border-radius:12px;background:#fff\">"
            f"<h2 style=\"margin:0 0 8px;font-size:18px\">{html.escape(str(row['title']))}</h2>"
            f"<p><strong>When:</strong> {html.escape(str(row['date_label']))} at "
            f"{html.escape(str(row['time_label']))}<br>"
            f"<strong>Where:</strong> {html.escape(str(row['location']))}<br>"
            f"<strong>F&amp;B:</strong> {html.escape(str(row['fnb_label']))}<br>"
            f"<strong>Interest:</strong> {hot_pick}{popularity}<br>"
            f"<strong>Source:</strong> {html.escape(str(row['source']))}</p>"
            f"<p>{html.escape(str(row['summary']))}</p>"
            f"<p><a href=\"{html.escape(str(row['url']), quote=True)}\">"
            "Register / view event</a></p>"
            "</article>"
        )
    if not cards:
        cards.append(
            "<p>No events matched the current topic, location, date, and timing filters.</p>"
        )
    extra = ""
    if len(events) > MAX_EMAIL_EVENTS:
        extra = f"<p>Plus {len(events) - MAX_EMAIL_EVENTS} more event(s) in the dashboard.</p>"
    return (
        "<!doctype html><html><body style=\"margin:0;background:#f4f7f9;color:#17212b;"
        "font-family:Arial,sans-serif\"><main style=\"max-width:680px;margin:auto;padding:24px\">"
        "<h1 style=\"margin-bottom:4px\">JJs Event Agent</h1>"
        f"<p>Found {len(events)} upcoming Singapore event(s). Updated "
        f"{generated_at:%d %b %Y, %-I:%M %p} SGT.</p>{''.join(cards)}{extra}</main></body></html>"
    )


def build_email_summary(
    events: list[Event], settings: Settings, generated_at: datetime
) -> EmailMessage:
    sender = settings.smtp_from or settings.smtp_username
    message = EmailMessage()
    message["Subject"] = (
        f"JJs Event Agent: {len(events)} upcoming Singapore event"
        f"{'s' if len(events) != 1 else ''}"
    )
    message["From"] = sender
    message["To"] = settings.email_recipient
    message.set_content(_build_text(events, generated_at))
    message.add_alternative(_build_html(events, generated_at), subtype="html")
    return message


def send_email_summary(
    events: list[Event], settings: Settings, generated_at: datetime
) -> bool:
    if not settings.email_enabled:
        return False

    required = {
        "EMAIL_RECIPIENT": settings.email_recipient,
        "SMTP_HOST": settings.smtp_host,
        "SMTP_USERNAME": settings.smtp_username,
        "SMTP_PASSWORD": settings.smtp_password,
        "SMTP_FROM": settings.smtp_from or settings.smtp_username,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        LOGGER.warning("Email summary skipped; missing configuration: %s", ", ".join(missing))
        return False
    if settings.smtp_security not in {"starttls", "ssl"}:
        LOGGER.warning("Email summary skipped; SMTP_SECURITY must be starttls or ssl")
        return False

    try:
        message = build_email_summary(events, settings, generated_at)
        context = ssl.create_default_context()
        client_class = smtplib.SMTP_SSL if settings.smtp_security == "ssl" else smtplib.SMTP
        with client_class(
            settings.smtp_host,
            settings.smtp_port,
            timeout=settings.http_timeout_seconds,
            **({"context": context} if settings.smtp_security == "ssl" else {}),
        ) as client:
            if settings.smtp_security == "starttls":
                client.ehlo()
                client.starttls(context=context)
                client.ehlo()
            client.login(settings.smtp_username, settings.smtp_password)
            client.send_message(message)
    except (OSError, smtplib.SMTPException, ValueError):
        LOGGER.exception("Email summary delivery failed")
        return False
    LOGGER.info("Email summary sent to %s", settings.email_recipient)
    return True
