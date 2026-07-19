from __future__ import annotations

import logging
from datetime import datetime
from urllib.parse import quote_plus, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from event_agent.config import Settings
from event_agent.extraction import (
    extract_attendance_metrics,
    extract_detail_page_events,
    extract_events_from_cards,
    extract_json_ld_events,
)
from event_agent.models import RawEvent, canonical_url
from event_agent.sources.browser_utils import parse_cookie_json

LOGGER = logging.getLogger(__name__)
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131 Safari/537.36"
)


def _is_event_url(url: str) -> bool:
    parts = urlsplit(url)
    return "eventbrite." in (parts.hostname or "").casefold() and parts.path.startswith("/e/")


def _candidate_cards(html: str, page_url: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    cards: list[dict[str, str]] = []
    seen: set[str] = set()
    for anchor in soup.select('a[href*="/e/"]'):
        href = urljoin(page_url, str(anchor.get("href", "")))
        normalized = canonical_url(href)
        if not _is_event_url(href) or normalized in seen:
            continue
        container = anchor.find_parent(["article", "li"]) or anchor.find_parent("div") or anchor
        text = container.get_text("\n", strip=True)
        heading = container.find(["h1", "h2", "h3", "h4"])
        title = heading.get_text(" ", strip=True) if heading else ""
        if len(text) < 20:
            continue
        seen.add(normalized)
        cards.append({"url": href, "text": text[:6000], "title": title})
    return cards


class EventbriteSource:
    name = "Eventbrite"

    @staticmethod
    def _urls(settings: Settings) -> tuple[str, ...]:
        query = quote_plus(" ".join(settings.keywords))
        return settings.eventbrite_search_urls or (
            f"https://www.eventbrite.sg/d/singapore--singapore/free--events/?q={query}",
        )

    def collect(self, settings: Settings) -> list[RawEvent]:
        cookies = parse_cookie_json(
            settings.eventbrite_cookies_json, default_domain=".eventbrite.sg"
        )
        now = datetime.now(settings.timezone)
        events: list[RawEvent] = []
        event_urls: list[str] = []
        listing_candidates: dict[str, list[RawEvent]] = {}
        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept-Language": "en-SG,en;q=0.9",
            }
        )
        for cookie in cookies:
            session.cookies.set(
                cookie["name"],
                cookie["value"],
                domain=cookie.get("domain") or ".eventbrite.sg",
                path=cookie.get("path") or "/",
            )

        for url in self._urls(settings):
            LOGGER.info("Fetching Eventbrite public Singapore search")
            response = session.get(url, timeout=settings.http_timeout_seconds)
            response.raise_for_status()
            listing_events = extract_json_ld_events(
                response.text,
                source=self.name,
                page_url=response.url,
                timezone=settings.timezone,
            )
            event_urls.extend(
                event.url for event in listing_events if _is_event_url(event.url)
            )
            cards = _candidate_cards(response.text, response.url)
            card_events = extract_events_from_cards(
                cards,
                source=self.name,
                reference_time=now,
                timezone=settings.timezone,
                location_hint="Singapore",
            )
            for event in card_events:
                if not _is_event_url(event.url):
                    continue
                event_urls.append(event.url)
                listing_candidates.setdefault(canonical_url(event.url), []).append(event)

        detail_urls = list(dict.fromkeys(canonical_url(url) for url in event_urls))[
            : settings.eventbrite_max_events
        ]
        LOGGER.info("Eventbrite: inspecting %d event detail pages", len(detail_urls))
        for url in detail_urls:
            try:
                response = session.get(url, timeout=settings.http_timeout_seconds)
                response.raise_for_status()
                html = response.text
                body_text = BeautifulSoup(html, "html.parser").get_text("\n", strip=True)
                structured = extract_detail_page_events(
                    html,
                    source=self.name,
                    page_url=response.url,
                    timezone=settings.timezone,
                )
                metrics = extract_attendance_metrics(body_text)
                overview = max(
                    (event.description for event in structured),
                    key=len,
                    default="",
                )
                for candidate in listing_candidates.get(canonical_url(url), []):
                    candidate.description = overview
                    candidate.metadata["overview_source"] = "event-detail-page"
                    candidate.metadata.update(metrics)
                    events.append(candidate)
                for event in structured:
                    event.metadata.update(metrics)
                    event.raw_text = body_text[:20_000]
                events.extend(structured)
            except Exception as exc:
                LOGGER.warning("Eventbrite detail failed (%s)", type(exc).__name__)
        return events
