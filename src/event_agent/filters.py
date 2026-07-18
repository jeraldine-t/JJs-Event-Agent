from __future__ import annotations

import re
from datetime import datetime, time, timedelta
from urllib.parse import urlsplit

from event_agent.models import Event, FilterReport, RawEvent, canonical_url

KEYWORD_PATTERNS: dict[str, re.Pattern[str]] = {
    "AI": re.compile(r"\b(?:AI|artificial intelligence|machine learning|generative AI)\b", re.I),
    "Tech": re.compile(r"\b(?:tech|technology|software|developer|startup|digital)\b", re.I),
    "Robotics": re.compile(r"\b(?:robotics?|robots?|automation)\b", re.I),
    "Marketing": re.compile(r"\b(?:marketing|brand(?:ing)?|growth|advertising)\b", re.I),
    "Business": re.compile(r"\b(?:business|entrepreneur|founder|commerce|enterprise)\b", re.I),
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
    ("Networking", re.compile(r"\bnetworking\b", re.I)),
)

SINGAPORE_RE = re.compile(
    r"\b(?:singapore|sg|one[- ]north|raffles place|marina bay|orchard|bugis|"
    r"tanjong pagar|clarke quay|suntec|jurong|paya lebar|changi)\b",
    re.I,
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


def _valid_time_window(start_at: datetime) -> bool:
    local_time = start_at.timetz().replace(tzinfo=None)
    if start_at.weekday() < 5:
        return local_time > time(18, 0)
    return time(6, 0) <= local_time < time(18, 0)


def _dedupe_key(event: Event) -> tuple[str, str]:
    url = canonical_url(event.url)
    hostname = urlsplit(url).hostname or ""
    if url and hostname:
        return ("url", url.casefold())
    normalized_title = re.sub(r"\W+", " ", event.title.casefold()).strip()
    return ("title-time", f"{normalized_title}|{event.start_at:%Y-%m-%dT%H:%M}")


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
        if not free_evidence:
            report.reject("not-explicitly-free")
            continue
        if raw.start_at is None:
            report.reject("missing-date")
            continue
        start_at = raw.start_at.astimezone(now.tzinfo)
        if not now <= start_at <= latest:
            report.reject("date-range")
            continue
        if not _valid_time_window(start_at):
            report.reject("time-window")
            continue
        perk_text = "\n".join(
            value for value in (raw.title, raw.description, raw.raw_text) if value
        )
        if raw.location:
            perk_text = perk_text.replace(raw.location, " ")
        perks = _perks(perk_text)
        score = len(perks) * 20 + len(matched_keywords) * 3
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
                location=raw.location.strip() or "Singapore",
                keywords=matched_keywords,
                perks=perks,
                free_evidence=free_evidence,
                score=score,
            )
        )

    unique: dict[tuple[str, str], Event] = {}
    for event in accepted:
        key = _dedupe_key(event)
        existing = unique.get(key)
        if existing is None or event.score > existing.score:
            unique[key] = event
        else:
            report.reject("duplicate")
    result = sorted(unique.values(), key=lambda event: (-event.score, event.start_at, event.title))
    report.accepted = len(result)
    return result, report
