from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

from telethon import TelegramClient, functions, types
from telethon.sessions import StringSession

from event_agent.config import Settings
from event_agent.extraction import extract_event_from_text
from event_agent.models import RawEvent
from event_agent.sources.base import SourceNotConfigured

LOGGER = logging.getLogger(__name__)


def _message_urls(message: types.Message) -> list[str]:
    urls: list[str] = []
    for entity in message.entities or []:
        if isinstance(entity, types.MessageEntityTextUrl):
            urls.append(entity.url)
    markup = message.reply_markup
    for row in getattr(markup, "rows", []) or []:
        for button in getattr(row, "buttons", []) or []:
            url = getattr(button, "url", None)
            if url:
                urls.append(url)
    return urls


class TelegramUserSource:
    name = "Telegram"

    def collect(self, settings: Settings) -> list[RawEvent]:
        if not (
            settings.telegram_api_id
            and settings.telegram_api_hash
            and settings.telegram_session_string
        ):
            raise SourceNotConfigured(
                "set TELEGRAM_API_ID, TELEGRAM_API_HASH, and TELEGRAM_SESSION_STRING"
            )
        return asyncio.run(self._collect(settings))

    async def _collect(self, settings: Settings) -> list[RawEvent]:
        now = datetime.now(settings.timezone)
        cutoff = now - timedelta(days=settings.message_lookback_days)
        client = TelegramClient(
            StringSession(settings.telegram_session_string),
            settings.telegram_api_id,
            settings.telegram_api_hash,
        )
        events: list[RawEvent] = []
        failed_channels = 0
        async with client:
            for channel_name in settings.telegram_channels:
                try:
                    entity = await client.get_entity(channel_name)
                    result = await client(
                        functions.messages.GetForumTopicsRequest(
                            peer=entity,
                            offset_date=None,
                            offset_id=0,
                            offset_topic=0,
                            limit=100,
                            q=settings.telegram_topic_name,
                        )
                    )
                    topics = [
                        topic
                        for topic in result.topics
                        if getattr(topic, "title", "").casefold()
                        == settings.telegram_topic_name.casefold()
                    ]
                    if not topics:
                        LOGGER.warning(
                            "Telegram @%s has no topic named %s",
                            channel_name,
                            settings.telegram_topic_name,
                        )
                        continue
                    for topic in topics:
                        async for message in client.iter_messages(
                            entity, reply_to=topic.id, limit=300
                        ):
                            if message.date is None:
                                continue
                            message_date = message.date.astimezone(settings.timezone)
                            if message_date < cutoff:
                                break
                            text = message.raw_text or ""
                            urls = _message_urls(message)
                            if urls:
                                text = f"{text}\n" + "\n".join(urls)
                            event = extract_event_from_text(
                                text,
                                source=(
                                    f"Telegram · @{channel_name} / "
                                    f"{settings.telegram_topic_name}"
                                ),
                                default_url=f"https://t.me/{channel_name}/{message.id}",
                                reference_time=now,
                                timezone=settings.timezone,
                            )
                            if event:
                                events.append(event)
                except Exception as exc:
                    failed_channels += 1
                    LOGGER.warning("Telegram channel @%s failed: %s", channel_name, exc)
        if failed_channels == len(settings.telegram_channels):
            raise RuntimeError("All configured Telegram channels failed")
        return events
