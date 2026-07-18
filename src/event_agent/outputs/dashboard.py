from __future__ import annotations

import re
from datetime import datetime
from itertools import groupby
from pathlib import Path

from bs4 import BeautifulSoup
from jinja2 import Environment, PackageLoader

from event_agent.models import Event, FilterReport, SourceStatus

FNB_PERKS = frozenset(
    {
        "Free food",
        "Free drinks",
        "Pizza",
        "Beer",
        "Wine",
        "Refreshments",
        "Buffet",
        "Light bites",
    }
)
PRIVATE_TEXT_SOURCES = frozenset({"linkedin", "whatsapp"})
SUMMARY_WORD_LIMIT = 99


def _trim_summary(text: str, limit: int = SUMMARY_WORD_LIMIT) -> str:
    cleaned = BeautifulSoup(text or "", "html.parser").get_text(" ", strip=True)
    cleaned = re.sub(r"https?://\S+", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    words = cleaned.split()
    if len(words) <= limit:
        return cleaned
    return " ".join(words[:limit]).rstrip(".,;:!?") + "…"


def _event_summary(event: Event) -> str:
    topics = ", ".join(event.keywords[:3]) or "professional"
    fallback = _trim_summary(
        f"A free {topics} event in {event.location}. It fits the curated "
        "Singapore timing window; open the registration page for the organizer's "
        "agenda and latest details."
    )
    if event.source.casefold() in PRIVATE_TEXT_SOURCES:
        return _trim_summary(
            f"A free {topics} event in Singapore, shared through {event.source}. "
            "Open the registration page for the organizer's public description and latest details."
        )
    summary = _trim_summary(event.description)
    if summary and not (
        summary.casefold().startswith(event.title.casefold())
        and len(summary.split()) < 40
    ):
        return summary
    return fallback


def _event_row(event: Event) -> dict:
    row = event.to_dict()
    fnb_perks = [perk for perk in event.perks if perk in FNB_PERKS]
    row.update(
        {
            "date_iso": event.start_at.strftime("%Y-%m-%d"),
            "date_label": event.start_at.strftime("%a, %d %b %Y"),
            "time_label": event.start_at.strftime("%-I:%M %p SGT"),
            "day_type": (
                "After-work" if event.start_at.weekday() < 5 else "Weekend daytime"
            ),
            "summary": _event_summary(event),
            "fnb_perks": fnb_perks,
            "has_fnb": bool(fnb_perks),
            "fnb_label": ", ".join(fnb_perks) if fnb_perks else "Not stated",
            "keywords": [
                keyword for keyword in event.keywords if keyword not in event.perks
            ],
        }
    )
    return row


def _calendar_months(events: list[Event]) -> list[dict]:
    chronological = sorted(events, key=lambda event: (event.start_at, -event.score, event.title))
    months: list[dict] = []
    for month_key, month_group in groupby(
        chronological, key=lambda event: event.start_at.strftime("%Y-%m")
    ):
        month_events = list(month_group)
        days: list[dict] = []
        for date_key, day_group in groupby(
            month_events, key=lambda event: event.start_at.strftime("%Y-%m-%d")
        ):
            day_events = list(day_group)
            start = day_events[0].start_at
            days.append(
                {
                    "date_key": date_key,
                    "weekday": start.strftime("%A"),
                    "day_number": start.strftime("%d"),
                    "date_label": start.strftime("%d %B %Y"),
                    "events": [_event_row(event) for event in day_events],
                }
            )
        months.append(
            {
                "month_key": month_key,
                "month_label": month_events[0].start_at.strftime("%B %Y"),
                "event_count": len(month_events),
                "days": days,
            }
        )
    return months


def render_dashboard(
    events: list[Event],
    statuses: list[SourceStatus],
    report: FilterReport,
    *,
    generated_at: datetime,
    output_path: Path,
) -> None:
    environment = Environment(
        loader=PackageLoader("event_agent", "templates"),
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = environment.get_template("index.html.j2")
    fnb_count = sum(bool(FNB_PERKS.intersection(event.perks)) for event in events)
    rendered = template.render(
        events=[_event_row(event) for event in events],
        calendar_months=_calendar_months(events),
        statuses=[status.to_dict() for status in statuses],
        report=report,
        generated_at=generated_at.strftime("%d %b %Y, %-I:%M %p SGT"),
        source_names=sorted({event.source for event in events}),
        breakdowns={
            "fnb": fnb_count,
            "weekday": sum(event.start_at.weekday() < 5 for event in events),
            "weekend": sum(event.start_at.weekday() >= 5 for event in events),
            "networking": sum("Networking" in event.perks for event in events),
        },
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(f"{output_path.suffix}.tmp")
    temporary.write_text(rendered, encoding="utf-8")
    temporary.replace(output_path)
