from __future__ import annotations

import html
import logging
from dataclasses import dataclass

import requests

from event_agent.config import Settings
from event_agent.models import Event

LOGGER = logging.getLogger(__name__)
MAX_MESSAGE_LENGTH = 3900


@dataclass(frozen=True, slots=True)
class NotificationResult:
    state: str
    sent_messages: int
    detail: str = ""


def _event_block(event: Event, index: int) -> str:
    perks = ", ".join(event.perks) if event.perks else "None explicitly mentioned"
    url = html.escape(event.url, quote=True)
    title = html.escape(event.title)
    return (
        f"<b>{index}. {title}</b>\n"
        f"🗓 {event.start_at.strftime('%a, %d %b %Y · %-I:%M %p SGT')}\n"
        f"📍 {html.escape(event.location)}\n"
        f"✨ {html.escape(perks)}\n"
        f"🔎 {html.escape(event.source)}\n"
        f"🔗 <a href=\"{url}\">Register / details</a>"
    )


def _chunks(events: list[Event]) -> list[str]:
    heading = f"<b>JJs Event Agent</b> · {len(events)} matching event(s)"
    if not events:
        return [f"{heading}\n\nNo qualifying events were found this run."]
    chunks: list[str] = []
    current = heading
    for index, event in enumerate(events, start=1):
        block = _event_block(event, index)
        if len(current) + len(block) + 2 > MAX_MESSAGE_LENGTH:
            chunks.append(current)
            current = block
        else:
            current = f"{current}\n\n{block}"
    chunks.append(current)
    return chunks


def send_notifications(events: list[Event], settings: Settings) -> NotificationResult:
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        detail = "set TELEGRAM_BOT_TOKEN and MY_TELEGRAM_CHAT_ID"
        if settings.require_telegram_output:
            raise RuntimeError(f"Telegram output is required: {detail}")
        LOGGER.warning("Telegram notification skipped: %s", detail)
        return NotificationResult("skipped", 0, detail)

    endpoint = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    sent = 0
    for message in _chunks(events):
        try:
            response = requests.post(
                endpoint,
                json={
                    "chat_id": settings.telegram_chat_id,
                    "text": message,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
                timeout=settings.http_timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            status = getattr(getattr(exc, "response", None), "status_code", "unknown")
            raise RuntimeError(f"Telegram delivery failed (HTTP {status})") from None
        if not payload.get("ok"):
            raise RuntimeError("Telegram Bot API rejected the message")
        sent += 1
    return NotificationResult("sent", sent)
