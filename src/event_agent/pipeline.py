from __future__ import annotations

import logging
from datetime import datetime

from event_agent.config import Settings
from event_agent.filters import curate_events
from event_agent.models import RawEvent, SourceStatus
from event_agent.outputs.dashboard import render_dashboard
from event_agent.outputs.telegram_bot import NotificationResult, send_notifications
from event_agent.sources.base import EventSource, SourceNotConfigured
from event_agent.sources.linkedin import LinkedInSource
from event_agent.sources.luma import LumaSource
from event_agent.sources.public_web import EventbriteSource, MeetupSource
from event_agent.sources.telegram_user import TelegramUserSource
from event_agent.sources.whatsapp import WhatsAppSource

LOGGER = logging.getLogger(__name__)


def _sources() -> dict[str, EventSource]:
    return {
        "linkedin": LinkedInSource(),
        "luma": LumaSource(),
        "eventbrite": EventbriteSource(),
        "meetup": MeetupSource(),
        "whatsapp": WhatsAppSource(),
        "telegram": TelegramUserSource(),
    }


def run_pipeline(
    settings: Settings, *, send_telegram: bool = True
) -> tuple[int, list[SourceStatus], NotificationResult]:
    now = datetime.now(settings.timezone)
    raw_events: list[RawEvent] = []
    statuses: list[SourceStatus] = []
    registry = _sources()
    for configured_name in settings.enabled_sources:
        source = registry.get(configured_name.casefold())
        if source is None:
            statuses.append(
                SourceStatus(configured_name, "failed", detail="unknown source name")
            )
            continue
        LOGGER.info("Collecting from %s", source.name)
        try:
            found = source.collect(settings)
            raw_events.extend(found)
            statuses.append(SourceStatus(source.name, "ok", found=len(found)))
        except SourceNotConfigured as exc:
            LOGGER.warning("%s skipped: %s", source.name, exc)
            statuses.append(SourceStatus(source.name, "skipped", detail=str(exc)))
        except Exception as exc:
            LOGGER.exception("%s collection failed", source.name)
            statuses.append(SourceStatus(source.name, "failed", detail=str(exc)[:240]))

    events, report = curate_events(
        raw_events,
        keywords=settings.keywords,
        now=now,
        lookahead_days=settings.lookahead_days,
    )
    render_dashboard(
        events,
        statuses,
        report,
        generated_at=now,
        output_path=settings.output_html,
    )
    LOGGER.info("Dashboard written to %s with %d events", settings.output_html, len(events))

    notification = (
        send_notifications(events, settings)
        if send_telegram
        else NotificationResult("skipped", 0, "disabled by command line")
    )
    failures = [status for status in statuses if status.state == "failed"]
    if failures and settings.source_failure_mode == "fail":
        names = ", ".join(status.source for status in failures)
        raise RuntimeError(f"Sources failed after outputs were generated: {names}")
    return len(events), statuses, notification

