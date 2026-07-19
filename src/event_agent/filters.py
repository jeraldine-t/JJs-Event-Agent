from __future__ import annotations

import re
from datetime import datetime, time, timedelta
from urllib.parse import urlsplit

from event_agent.models import Event, FilterReport, RawEvent, canonical_url

KEYWORD_PATTERNS: dict[str, re.Pattern[str]] = {
    "AI": re.compile(
        r"\b(?:AI|artificial intelligence|machine learning|deep learning|generative AI|"
        r"genAI|LLMs?|large language models?|AI agents?|agentic|NLP|computer vision)\b",
        re.I,
    ),
    "Data": re.compile(
        r"\b(?:data|database|analytics?|business intelligence|BI|data engineering|"
        r"data science|ClickHouse|Postgres(?:QL)?|SQL|Apache Iceberg|data platforms?)\b",
        re.I,
    ),
    "Tech": re.compile(
        r"\b(?:tech|technology|software|developers?|engineering|programming|coding|"
        r"startups?|digital|cloud|AWS|Azure|GCP|Google Cloud|open source|APIs?|DevOps|"
        r"developer tools?|cybersecurity|fintech|blockchain|web3|infrastructure|platforms?)\b",
        re.I,
    ),
    "Robotics": re.compile(r"\b(?:robotics?|robots?|automation)\b", re.I),
    "Product": re.compile(
        r"\b(?:product management|product managers?|product design|product-led|"
        r"prototyping|user research|customer experience|CX)\b",
        re.I,
    ),
    "Design": re.compile(
        r"\b(?:design|designers?|UX|UI|user experience|service design|design thinking)\b",
        re.I,
    ),
    "Marketing": re.compile(
        r"\b(?:marketing|brand(?:ing)?|growth|advertising|go-to-market|GTM|sales|"
        r"content strategy|communications?|SEO|CRM|e-?commerce|community building)\b",
        re.I,
    ),
    "Business": re.compile(
        r"\b(?:business|entrepreneurs?|founders?|commerce|enterprise|innovation|"
        r"leadership|strategy|venture|investors?|fundraising|professional development)\b",
        re.I,
    ),
    "Networking": re.compile(r"\b(?:networking|network with|connect with|meet fellow)\b", re.I),
}

PERK_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("Free food", re.compile(r"\bfree\s+food\b", re.I)),
    ("Free drinks", re.compile(r"\bfree\s+drinks?\b", re.I)),
    ("Pizza", re.compile(r"\bpizza\b", re.I)),
    ("Beer", re.compile(r"\bbeers?\b", re.I)),
    ("Wine", re.compile(r"\bwine\b", re.I)),
    ("Refreshments", re.compile(r"\brefreshments?\b", re.I)),
    ("Buffet", re.compile(r"\bbuffet\b", re.I)),
    ("Light bites", re.compile(r"\blight\s+bites?\b", re.I)),
    ("Dinner", re.compile(r"\b(?:dinner|dinner provided|dinner included)\b", re.I)),
    ("Networking", re.compile(r"\bnetworking\b", re.I)),
)

SINGAPORE_RE = re.compile(
    r"\b(?:singapore|sg|one[- ]north|raffles place|marina bay|orchard|bugis|"
    r"tanjong pagar|clarke quay|suntec|jurong|paya lebar|changi|mapletree business city|"
    r"pasir panjang|downtown|cbd|city hall|dhoby ghaut|somerset|river valley)\b",
    re.I,
)

PREFERRED_AREA_RE = re.compile(
    r"\b(?:mapletree business city|pasir panjang|downtown|cbd|raffles place|marina bay|"
    r"tanjong pagar|orchard|somerset|dhoby ghaut|city hall|river valley)\b",
    re.I,
)
PREFERRED_AREA_LABELS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("Mapletree Business City", re.compile(r"\bmapletree business city\b", re.I)),
    ("Downtown", re.compile(r"\b(?:downtown|cbd|raffles place|marina bay)\b", re.I)),
    ("Orchard", re.compile(r"\b(?:orchard|somerset|dhoby ghaut)\b", re.I)),
)

EXPLICIT_FREE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bfree\s+(?:admission|entry|event|ticket|tickets|registration|to attend)\b", re.I),
    re.compile(
        r"\b(?:admission|entry|event|ticket|tickets|registration)\s+(?:is|are)\s+free\b",
        re.I,
    ),
    re.compile(r"\bno\s+(?:charge|cost|entry fee|admission fee)\b", re.I),
    re.compile(r"\bcomplimentary\s+(?:admission|entry|ticket|registration)\b", re.I),
    re.compile(r"(?:^|\s)(?:SGD|S\$|\$)\s*0(?:\.00)?(?:\s|$)", re.I),
)

EXACT_FREE_VALUES = {"0", "0.00", "$0", "$0.00", "s$0", "sgd 0", "free"}
PRICE_AMOUNT_RE = re.compile(r"(?:SGD|S\$|\$)\s*(\d+(?:\.\d{1,2})?)", re.I)
PAID_TICKET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"\b(?:tickets?|admission|entry|registration)\b.{0,24}?"
        r"(?:SGD|S\$|\$)\s*(\d+(?:\.\d{1,2})?)",
        re.I,
    ),
    re.compile(
        r"(?:SGD|S\$|\$)\s*(\d+(?:\.\d{1,2})?).{0,16}?"
        r"\b(?:per\s+(?:person|pax)|for\s+members?|tickets?|admission|entry|registration)\b",
        re.I,
    ),
)


def _keywords(text: str, configured: tuple[str, ...]) -> tuple[str, ...]:
    result: list[str] = []
    for keyword in configured:
        pattern = KEYWORD_PATTERNS.get(keyword)
        known_match = bool(pattern and pattern.search(text))
        custom_match = bool(
            not pattern and re.search(rf"\b{re.escape(keyword)}\b", text, re.I)
        )
        if known_match or custom_match:
            result.append(keyword)
    return tuple(result)


def _perks(text: str) -> tuple[str, ...]:
    return tuple(label for label, pattern in PERK_PATTERNS if pattern.search(text))


def _free_evidence(raw: RawEvent, text: str) -> str:
    price = re.sub(r"\s+", " ", raw.price_text.strip().casefold())
    if price in EXACT_FREE_VALUES:
        return raw.price_text.strip() or "Free"
    if raw.metadata.get("structured_price") == 0:
        return "Structured ticket price: 0"
    for pattern in EXPLICIT_FREE_PATTERNS:
        match = pattern.search(" ".join((raw.price_text, text)))
        if match:
            return match.group(0).strip()
    return ""


def _positive_amount(match: re.Match[str]) -> bool:
    try:
        return float(match.group(1)) > 0
    except (TypeError, ValueError):
        return False


def _paid_evidence(raw: RawEvent, text: str) -> str:
    structured_price = raw.metadata.get("structured_price")
    try:
        if structured_price is not None and float(structured_price) > 0:
            return f"Structured ticket price: {structured_price}"
    except (TypeError, ValueError):
        pass
    for match in PRICE_AMOUNT_RE.finditer(raw.price_text):
        if _positive_amount(match):
            return match.group(0).strip()
    for pattern in PAID_TICKET_PATTERNS:
        for match in pattern.finditer(text):
            if _positive_amount(match):
                return match.group(0).strip()
    return ""


def _metric(raw: RawEvent, key: str) -> int | None:
    try:
        value = int(raw.metadata.get(key))
    except (TypeError, ValueError):
        return None
    return value if value >= 0 else None


def _display_location(raw_location: str, text: str) -> str:
    location = raw_location.strip() or "Singapore"
    for label, pattern in PREFERRED_AREA_LABELS:
        if pattern.search(text) and label.casefold() not in location.casefold():
            return f"{location}, {label}"
    return location


def _valid_time_window(start_at: datetime, *, preferred_area: bool = False) -> bool:
    local_time = start_at.timetz().replace(tzinfo=None)
    if start_at.weekday() < 5:
        return local_time > time(18, 0) or (preferred_area and local_time == time(18, 0))
    return time(6, 0) <= local_time < time(18, 0)


def _dedupe_key(event: Event) -> tuple[str, str]:
    url = canonical_url(event.url)
    hostname = urlsplit(url).hostname or ""
    if url and hostname:
        return ("url", url.casefold())
    normalized_title = re.sub(r"\W+", " ", event.title.casefold()).strip()
    return ("title-time", f"{normalized_title}|{event.start_at:%Y-%m-%dT%H:%M}")


def _event_quality(event: Event) -> tuple[int, int, int]:
    metrics = sum(
        value is not None
        for value in (event.attendee_count, event.capacity, event.seats_left)
    )
    return (event.score, metrics, len(event.description))


def curate_events(
    raw_events: list[RawEvent],
    *,
    keywords: tuple[str, ...],
    now: datetime,
    lookahead_days: int,
) -> tuple[list[Event], FilterReport]:
    report = FilterReport()
    accepted: list[Event] = []
    latest = now + timedelta(days=lookahead_days)
    for raw in raw_events:
        if (
            not raw.description.strip()
            or raw.metadata.get("overview_source") != "event-detail-page"
        ):
            report.reject("missing-overview")
            continue
        text = "\n".join(
            value for value in (raw.title, raw.description, raw.raw_text, raw.location) if value
        )
        matched_keywords = _keywords(text, keywords)
        if not matched_keywords:
            report.reject("keyword")
            continue
        location_text = " ".join((raw.location, text))
        if not SINGAPORE_RE.search(location_text):
            report.reject("location")
            continue
        free_evidence = _free_evidence(raw, text)
        if not free_evidence and _paid_evidence(raw, text):
            report.reject("explicitly-paid")
            continue
        if raw.start_at is None:
            report.reject("missing-date")
            continue
        start_at = raw.start_at.astimezone(now.tzinfo)
        if not now <= start_at <= latest:
            report.reject("date-range")
            continue
        preferred_area = bool(PREFERRED_AREA_RE.search(location_text))
        if not _valid_time_window(start_at, preferred_area=preferred_area):
            report.reject("time-window")
            continue
        perk_text = "\n".join(
            value for value in (raw.title, raw.description, raw.raw_text) if value
        )
        if raw.location:
            perk_text = perk_text.replace(raw.location, " ")
        perks = _perks(perk_text)
        score = len(perks) * 20 + len(matched_keywords) * 3
        if preferred_area:
            score += 12
        if any(perk in perks for perk in ("Free food", "Free drinks", "Pizza", "Beer", "Wine")):
            score += 15
        accepted.append(
            Event(
                source=raw.source,
                title=raw.title.strip() or "Untitled event",
                description=raw.description.strip(),
                url=canonical_url(raw.url),
                start_at=start_at,
                end_at=raw.end_at.astimezone(now.tzinfo) if raw.end_at else None,
                location=_display_location(raw.location, location_text),
                keywords=matched_keywords,
                perks=perks,
                free_evidence=free_evidence,
                score=score,
                attendee_count=_metric(raw, "attendee_count"),
                capacity=_metric(raw, "capacity"),
                seats_left=_metric(raw, "seats_left"),
                registration_status=str(raw.metadata.get("registration_status", "")),
            )
        )

    unique: dict[tuple[str, str], Event] = {}
    for event in accepted:
        key = _dedupe_key(event)
        existing = unique.get(key)
        if existing is None or _event_quality(event) > _event_quality(existing):
            unique[key] = event
        else:
            report.reject("duplicate")
    result = sorted(unique.values(), key=lambda event: (-event.score, event.start_at, event.title))
    report.accepted = len(result)
    return result, report
