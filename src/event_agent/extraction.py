from __future__ import annotations

import json
import re
from collections.abc import Iterable, Iterator
from contextlib import suppress
from datetime import datetime
from typing import Any
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import dateparser
from bs4 import BeautifulSoup
from dateparser.search import search_dates
from dateutil import parser as dateutil_parser

from event_agent.models import RawEvent

URL_RE = re.compile(r"https?://[^\s<>\]\[\)\(\"']+", re.IGNORECASE)
PRICE_LINE_RE = re.compile(
    r"(?:\bfree\b|\$\s*0\b|\bsgd\s*0\b|\bcomplimentary\b|\bno\s+(?:charge|cost)\b)",
    re.IGNORECASE,
)
LOCATION_RE = re.compile(
    r"\b(?:singapore|sg|one[- ]north|raffles place|marina bay|orchard|bugis|"
    r"tanjong pagar|clarke quay|suntec|jurong|paya lebar|changi)\b",
    re.IGNORECASE,
)
DATE_TIME_LINE_RE = re.compile(
    r"\b(?:Mon(?:day)?|Tue(?:sday)?|Wed(?:nesday)?|Thu(?:rsday)?|Fri(?:day)?|"
    r"Sat(?:urday)?|Sun(?:day)?|Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|"
    r"Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?)\b.*\b\d{1,2}(?::\d{2})?\s*(?:AM|PM)\b",
    re.IGNORECASE,
)
ATTENDEE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"\b(\d{1,3}(?:,\d{3})*)\s+(?:going|attending|attendees?|rsvp(?:'d|s)?)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:going|attending|attendees?|rsvp(?:'d|s)?)[\s:]+"
        r"(\d{1,3}(?:,\d{3})*)\b",
        re.IGNORECASE,
    ),
)
SEATS_LEFT_RE = re.compile(
    r"\b(\d{1,4})\s+(?:seats?|spots?|tickets?)\s+(?:left|remaining|available)\b",
    re.IGNORECASE,
)
CAPACITY_RE = re.compile(
    r"\b(?:event\s+)?capacity(?:\s+of|\s*:)?\s*(\d{1,5})\b",
    re.IGNORECASE,
)
WAITLIST_RE = re.compile(
    r"\b(?:sold\s*out|event\s+full|waiting\s+list|waitlist|join\s+(?:the\s+)?waiting\s+list)\b",
    re.IGNORECASE,
)
CLOSED_RE = re.compile(
    r"\b(?:registration\s+closed|not\s+currently\s+taking\s+registrations)\b",
    re.IGNORECASE,
)
OVERVIEW_HEADINGS = {
    "about event",
    "about the event",
    "about this event",
    "event details",
    "event overview",
    "overview",
}
OVERVIEW_SELECTORS = (
    ".event-about-card",
    '[data-testid="event-description"]',
    '[data-automation="about-this-event-sc"]',
    '[itemprop="description"]',
    ".event-description",
    ".event-detail-description",
)


def parse_datetime(value: Any, timezone: ZoneInfo) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = dateutil_parser.parse(str(value))
        except (TypeError, ValueError, OverflowError):
            return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone)
    return parsed.astimezone(timezone)


def _nonnegative_int(value: Any) -> int | None:
    try:
        parsed = int(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def extract_attendance_metrics(text: str) -> dict[str, Any]:
    """Extract conservative public signup, capacity, and registration signals."""
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    metrics: dict[str, Any] = {}
    for pattern in ATTENDEE_PATTERNS:
        match = pattern.search(cleaned)
        if match:
            metrics["attendee_count"] = _nonnegative_int(match.group(1))
            break
    seats_match = SEATS_LEFT_RE.search(cleaned)
    if seats_match:
        metrics["seats_left"] = _nonnegative_int(seats_match.group(1))
    capacity_match = CAPACITY_RE.search(cleaned)
    if capacity_match:
        metrics["capacity"] = _nonnegative_int(capacity_match.group(1))
    if WAITLIST_RE.search(cleaned):
        metrics["registration_status"] = "waitlist"
        metrics["seats_left"] = 0
    elif CLOSED_RE.search(cleaned):
        metrics["registration_status"] = "closed"
    return {key: value for key, value in metrics.items() if value is not None}


def _walk_json(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_json(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_json(child)


def _is_event_schema(item: dict[str, Any]) -> bool:
    item_type = item.get("@type")
    if isinstance(item_type, list):
        return any(str(value).casefold() == "event" for value in item_type)
    return str(item_type).casefold() == "event"


def _location_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if not isinstance(value, dict):
        return ""
    parts: list[str] = []
    if value.get("name"):
        parts.append(str(value["name"]))
    address = value.get("address")
    if isinstance(address, str):
        parts.append(address)
    elif isinstance(address, dict):
        address_keys = (
            "streetAddress",
            "addressLocality",
            "addressRegion",
            "postalCode",
            "addressCountry",
        )
        for key in address_keys:
            if address.get(key):
                parts.append(str(address[key]))
    return ", ".join(dict.fromkeys(part.strip() for part in parts if part.strip()))


def _price_text(item: dict[str, Any]) -> str:
    offers = item.get("offers")
    if not offers:
        return ""
    values = offers if isinstance(offers, list) else [offers]
    prices: list[str] = []
    for offer in values:
        if not isinstance(offer, dict):
            continue
        price = offer.get("price")
        low = offer.get("lowPrice")
        currency = offer.get("priceCurrency", "")
        availability = offer.get("availability", "")
        if price is not None:
            prices.append(f"{currency} {price}".strip())
        elif low is not None:
            prices.append(f"{currency} {low}".strip())
        if availability:
            prices.append(str(availability))
    return "; ".join(prices)


def _json_ld_metadata(item: dict[str, Any]) -> dict[str, Any]:
    metadata: dict[str, Any] = {"extraction": "json-ld"}
    capacity = _nonnegative_int(item.get("maximumAttendeeCapacity"))
    seats_left = _nonnegative_int(item.get("remainingAttendeeCapacity"))
    if capacity is not None:
        metadata["capacity"] = capacity
    if seats_left is not None:
        metadata["seats_left"] = seats_left
    if capacity is not None and seats_left is not None:
        metadata["attendee_count"] = max(capacity - seats_left, 0)

    offers = item.get("offers")
    values = offers if isinstance(offers, list) else [offers]
    prices = [
        offer.get("price", offer.get("lowPrice"))
        for offer in values
        if isinstance(offer, dict)
        and offer.get("price", offer.get("lowPrice")) is not None
    ]
    if prices:
        with suppress(TypeError, ValueError):
            metadata["structured_price"] = min(float(price) for price in prices)
    availability = " ".join(
        str(offer.get("availability", ""))
        for offer in values
        if isinstance(offer, dict)
    )
    if "soldout" in availability.replace(" ", "").casefold():
        metadata["registration_status"] = "waitlist"
        metadata["seats_left"] = 0
    return metadata


def extract_json_ld_events(
    html: str,
    *,
    source: str,
    page_url: str,
    timezone: ZoneInfo,
) -> list[RawEvent]:
    """Extract schema.org Event objects from an HTML document."""
    soup = BeautifulSoup(html, "html.parser")
    found: list[RawEvent] = []
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            payload = json.loads(script.string or script.get_text() or "null")
        except (json.JSONDecodeError, TypeError):
            continue
        for item in _walk_json(payload):
            if not _is_event_schema(item):
                continue
            title = str(item.get("name") or "Untitled event").strip()
            description = BeautifulSoup(
                str(item.get("description") or ""), "html.parser"
            ).get_text(" ", strip=True)
            url = urljoin(page_url, str(item.get("url") or page_url))
            location = _location_text(item.get("location"))
            found.append(
                RawEvent(
                    source=source,
                    title=title,
                    description=description,
                    url=url,
                    start_at=parse_datetime(item.get("startDate"), timezone),
                    end_at=parse_datetime(item.get("endDate"), timezone),
                    location=location,
                    price_text=_price_text(item),
                    raw_text=" ".join((title, description, location)),
                    metadata=_json_ld_metadata(item),
                )
            )
    return found


def extract_event_overview(html: str) -> str:
    """Extract the organizer-written overview from a known event-detail section."""
    soup = BeautifulSoup(html, "html.parser")
    for selector in OVERVIEW_SELECTORS:
        node = soup.select_one(selector)
        if node is None:
            continue
        text = re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip()
        for heading in OVERVIEW_HEADINGS:
            if text.casefold().startswith(heading):
                text = text[len(heading) :].lstrip(" :-–—")
                break
        if len(text.split()) >= 8:
            return text[:20_000]

    for node in soup.find_all(["h2", "h3", "h4", "div"]):
        label = re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip().casefold()
        if label not in OVERVIEW_HEADINGS:
            continue
        sibling = node.find_next_sibling()
        if sibling is None:
            continue
        text = re.sub(r"\s+", " ", sibling.get_text(" ", strip=True)).strip()
        if len(text.split()) >= 8:
            return text[:20_000]
    return ""


def extract_detail_page_events(
    html: str,
    *,
    source: str,
    page_url: str,
    timezone: ZoneInfo,
) -> list[RawEvent]:
    """Extract structured events and fill missing descriptions from the page overview."""
    events = extract_json_ld_events(
        html,
        source=source,
        page_url=page_url,
        timezone=timezone,
    )
    overview = extract_event_overview(html)
    for event in events:
        if not event.description:
            event.description = overview
        event.metadata["overview_source"] = "event-detail-page"
    return events


def _best_title(lines: list[str]) -> str:
    for line in lines:
        candidate = re.sub(r"\s+", " ", line).strip(" -–—•")
        if not candidate or URL_RE.fullmatch(candidate) or len(candidate) < 4:
            continue
        if PRICE_LINE_RE.fullmatch(candidate) or LOCATION_RE.fullmatch(candidate):
            continue
        return candidate[:180]
    return "Event shared in message"


def _find_future_datetime(
    text: str,
    *,
    reference_time: datetime,
    timezone: ZoneInfo,
) -> datetime | None:
    settings = {
        "TIMEZONE": str(timezone),
        "TO_TIMEZONE": str(timezone),
        "RETURN_AS_TIMEZONE_AWARE": True,
        "PREFER_DATES_FROM": "future",
        "RELATIVE_BASE": reference_time,
        "STRICT_PARSING": False,
    }
    line_values: list[datetime] = []
    for line in text.splitlines():
        candidate = re.sub(r"[•·]", " ", line)
        candidate = re.sub(r"\+\s*\d+\s+more.*$", "", candidate, flags=re.I).strip()
        if not DATE_TIME_LINE_RE.search(candidate):
            continue
        try:
            value = dateparser.parse(candidate, languages=["en"], settings=settings)
        except (TypeError, ValueError, OverflowError):
            value = None
        aware = parse_datetime(value, timezone)
        if aware and aware >= reference_time:
            line_values.append(aware)
    if line_values:
        return min(line_values)

    try:
        matches = search_dates(text, languages=["en"], settings=settings) or []
    except (TypeError, ValueError, OverflowError):
        return None
    plausible: list[datetime] = []
    for _matched_text, value in matches:
        aware = parse_datetime(value, timezone)
        if aware and aware >= reference_time:
            plausible.append(aware)
    return min(plausible, default=None)


def extract_event_from_text(
    text: str,
    *,
    source: str,
    default_url: str,
    reference_time: datetime,
    timezone: ZoneInfo,
    location_hint: str = "",
) -> RawEvent | None:
    """Turn an event-like social message into a conservative raw candidate."""
    cleaned = re.sub(r"[\u200b-\u200f\ufeff]", "", text or "").strip()
    if not cleaned:
        return None
    start_at = _find_future_datetime(cleaned, reference_time=reference_time, timezone=timezone)
    if start_at is None:
        return None
    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    urls = [match.rstrip(".,;:!?") for match in URL_RE.findall(cleaned)]
    location_lines = [line for line in lines[1:] if LOCATION_RE.search(line)]
    if not location_lines:
        location_lines = [line for line in lines if LOCATION_RE.search(line)]
    price_lines = [line for line in lines[1:] if PRICE_LINE_RE.search(line)]
    if not price_lines:
        price_lines = [line for line in lines if PRICE_LINE_RE.search(line)]
    return RawEvent(
        source=source,
        title=_best_title(lines),
        description=cleaned[:4000],
        url=urls[0] if urls else default_url,
        start_at=start_at,
        location="; ".join(location_lines[:2]) or location_hint,
        price_text="; ".join(price_lines[:2]),
        raw_text=cleaned,
        metadata={"extraction": "message-text", "location_hint": bool(location_hint)},
    )


def extract_events_from_cards(
    cards: Iterable[dict[str, str]],
    *,
    source: str,
    reference_time: datetime,
    timezone: ZoneInfo,
    location_hint: str = "",
) -> list[RawEvent]:
    events: list[RawEvent] = []
    for card in cards:
        event = extract_event_from_text(
            card.get("text", ""),
            source=source,
            default_url=card.get("url", ""),
            reference_time=reference_time,
            timezone=timezone,
            location_hint=location_hint,
        )
        if event:
            # Listing-card text mixes titles, dates, locations, and UI labels. It remains
            # useful for filtering, but it is not an organizer-authored event description.
            event.description = (card.get("description") or "").strip()
            events.append(event)
    return events
