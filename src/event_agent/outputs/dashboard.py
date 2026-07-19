from __future__ import annotations

import json
import re
from datetime import datetime
from itertools import groupby
from pathlib import Path

from bs4 import BeautifulSoup
from jinja2 import Environment, PackageLoader

from event_agent.models import Event, FilterReport, SourceStatus

FNB_PERKS = (
    "Free food",
    "Free drinks",
    "Pizza",
    "Beer",
    "Wine",
    "Refreshments",
    "Buffet",
    "Light bites",
    "Dinner",
)
SUMMARY_WORD_LIMIT = 99
DEFAULT_SOURCE_OPTIONS = (
    ("linkedin", "LinkedIn"),
    ("eventbrite", "Eventbrite"),
    ("lu.ma", "Lu.ma · Singapore"),
    ("meetup", "Meetup"),
    ("gdg", "Google Developer Groups"),
)


def _optional_int(value: object) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def load_dashboard_events(output_path: Path) -> list[Event]:
    """Recover previously published events so the calendar remains an archive."""
    if not output_path.exists():
        return []

    try:
        soup = BeautifulSoup(output_path.read_text(encoding="utf-8"), "html.parser")
        payload = soup.select_one("script#calendar-data")
        rows = json.loads(payload.get_text() if payload else "[]")
    except (OSError, json.JSONDecodeError):
        return []

    events: list[Event] = []
    for row in rows if isinstance(rows, list) else []:
        try:
            events.append(
                Event(
                    source=str(row["source"]),
                    title=str(row["title"]),
                    description=str(row["description"]),
                    url=str(row["url"]),
                    start_at=datetime.fromisoformat(str(row["start_at"])),
                    location=str(row["location"]),
                    keywords=tuple(str(value) for value in row.get("keywords", [])),
                    perks=tuple(str(value) for value in row.get("perks", [])),
                    free_evidence=str(row.get("free_evidence", "")),
                    score=int(row.get("score", 0)),
                    end_at=(
                        datetime.fromisoformat(str(row["end_at"]))
                        if row.get("end_at")
                        else None
                    ),
                    attendee_count=_optional_int(row.get("attendee_count")),
                    capacity=_optional_int(row.get("capacity")),
                    seats_left=_optional_int(row.get("seats_left")),
                    registration_status=str(row.get("registration_status", "")),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return events


def merge_event_archive(current: list[Event], archived: list[Event]) -> list[Event]:
    """Retain published events forever while favoring freshly scraped details."""
    by_id = {event.event_id: event for event in archived}
    by_id.update({event.event_id: event for event in current})
    return sorted(by_id.values(), key=lambda event: (event.start_at, event.title.casefold()))


def _trim_summary(text: str, limit: int = SUMMARY_WORD_LIMIT) -> str:
    cleaned = BeautifulSoup(text or "", "html.parser").get_text(" ", strip=True)
    cleaned = re.sub(r"https?://\S+", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    words = cleaned.split()
    if len(words) <= limit:
        return cleaned
    return " ".join(words[:limit]).rstrip(".,;:!?") + "…"


def _overview_summary(event: Event) -> str:
    return _trim_summary(event.description)


def _popularity(event: Event) -> dict[str, object]:
    details: list[str] = []
    if event.attendee_count is not None:
        details.append(f"{event.attendee_count:,} going")
    if event.seats_left is not None:
        if event.seats_left == 0:
            details.append("Waitlist / full")
        else:
            details.append(f"{event.seats_left:,} seats left")
    elif event.registration_status == "closed":
        details.append("Registration closed")
    elif event.capacity is not None and event.attendee_count is None:
        details.append(f"Capacity {event.capacity:,}")
    hot_pick = bool(
        (event.attendee_count is not None and event.attendee_count >= 50)
        or (event.seats_left is not None and event.seats_left <= 10)
        or event.registration_status == "waitlist"
    )
    return {"popularity_label": " · ".join(details), "hot_pick": hot_pick}


def _event_row(event: Event) -> dict:
    row = event.to_dict()
    fnb_perks = [perk for perk in event.perks if perk in FNB_PERKS]
    summary = _overview_summary(event)
    row.update(
        {
            "date_iso": event.start_at.strftime("%Y-%m-%d"),
            "date_label": event.start_at.strftime("%a, %d %b %Y"),
            "time_label": event.start_at.strftime("%-I:%M %p SGT"),
            "compact_time_label": event.start_at.strftime("%-I:%M%p").lower(),
            "day_type": (
                "After-work" if event.start_at.weekday() < 5 else "Weekend daytime"
            ),
            "summary": summary,
            "fnb_perks": fnb_perks,
            "has_fnb": bool(fnb_perks),
            "fnb_label": ", ".join(fnb_perks) if fnb_perks else "Not stated",
            "keywords": [
                keyword for keyword in event.keywords if keyword not in event.perks
            ],
        }
    )
    row.update(_popularity(event))
    return row


def _source_options(events: list[Event], statuses: list[SourceStatus]) -> list[dict[str, str]]:
    options = {value: label for value, label in DEFAULT_SOURCE_OPTIONS}
    for name in [event.source for event in events] + [status.source for status in statuses]:
        value = name.casefold()
        options.setdefault(value, name)
    return [{"value": value, "label": label} for value, label in options.items()]


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
    rendered = template.render(
        events=[_event_row(event) for event in events],
        calendar_months=_calendar_months(events),
        statuses=[status.to_dict() for status in statuses],
        report=report,
        generated_at=generated_at.strftime("%d %b %Y · %-I:%M %p SGT"),
        generated_date=generated_at.strftime("%Y-%m-%d"),
        initial_month=generated_at.strftime("%Y-%m"),
        source_options=_source_options(events, statuses),
        fnb_types=FNB_PERKS,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(f"{output_path.suffix}.tmp")
    temporary.write_text(rendered, encoding="utf-8")
    temporary.replace(output_path)
