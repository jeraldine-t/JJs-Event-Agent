from __future__ import annotations

import logging
from datetime import datetime

from event_agent.config import Settings
from event_agent.filters import curate_events
from event_agent.models import RawEvent, SourceStatus
from event_agent.outputs.dashboard import (
    load_dashboard_events,
    merge_event_archive,
    render_dashboard,
)
from event_agent.outputs.email import send_email_summary
from event_agent.sources.base import EventSource, SourceNotConfigured
from event_agent.sources.eventbrite import EventbriteSource
from event_agent.sources.gdg import GDGSource
from event_agent.sources.linkedin import LinkedInSource
from event_agent.sources.luma import LumaSource
from event_agent.sources.public_web import MeetupSource
from event_agent.sources.whatsapp import WhatsAppSource

LOGGER = logging.getLogger(__name__)


def _sources() -> dict[str, EventSource]:
    return {
        "linkedin": LinkedInSource(),
        "luma": LumaSource(),
        "eventbrite": EventbriteSource(),
        "gdg": GDGSource(),
        "meetup": MeetupSource(),
        "whatsapp": WhatsAppSource(),
    }


def run_pipeline(settings: Settings) -> tuple[int, list[SourceStatus]]:
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

    current_events, report = curate_events(
        raw_events,
        keywords=settings.keywords,
        now=now,
        lookahead_days=settings.lookahead_days,
    )
    archived_events = load_dashboard_events(settings.output_html)
    events = merge_event_archive(current_events, archived_events)
    report.accepted = len(events)
    render_dashboard(
        events,
        statuses,
        report,
        generated_at=now,
        output_path=settings.output_html,
    )
    LOGGER.info(
        "Dashboard written to %s with %d events (%d current, %d previously published)",
        settings.output_html,
        len(events),
        len(current_events),
        len(archived_events),
    )
    send_email_summary(current_events, settings, now)

    failures = [status for status in statuses if status.state == "failed"]
    if failures and settings.source_failure_mode == "fail":
        names = ", ".join(status.source for status in failures)
        raise RuntimeError(f"Sources failed after outputs were generated: {names}")
    return len(events), statuses
