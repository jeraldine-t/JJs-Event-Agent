from __future__ import annotations

import logging
from datetime import datetime
from urllib.parse import quote_plus, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from event_agent.config import Settings
from event_agent.extraction import extract_events_from_cards, extract_json_ld_events
from event_agent.models import RawEvent

LOGGER = logging.getLogger(__name__)
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131 Safari/537.36"
)


def _candidate_cards(html: str, page_url: str, host_hint: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    cards: list[dict[str, str]] = []
    seen: set[str] = set()
    for anchor in soup.select("a[href]"):
        href = urljoin(page_url, str(anchor.get("href", "")))
        if host_hint not in (urlsplit(href).hostname or ""):
            continue
        container = anchor.find_parent(["article", "li"]) or anchor.find_parent("div") or anchor
        text = container.get_text("\n", strip=True)
        if href in seen or len(text) < 20:
            continue
        seen.add(href)
        cards.append({"url": href, "text": text[:6000]})
    return cards


class MeetupSource:
    name = "Meetup"

    @staticmethod
    def _urls(settings: Settings) -> tuple[str, ...]:
        query = quote_plus(" ".join(settings.keywords))
        return settings.meetup_search_urls or (
            f"https://www.meetup.com/find/?keywords={query}&location=sg--Singapore&source=EVENTS",
        )

    def collect(self, settings: Settings) -> list[RawEvent]:
        now = datetime.now(settings.timezone)
        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept-Language": "en-SG,en;q=0.9",
            }
        )
        events: list[RawEvent] = []
        for url in self._urls(settings):
            LOGGER.info("Fetching Meetup search page: %s", url)
            response = session.get(url, timeout=settings.http_timeout_seconds)
            response.raise_for_status()
            events.extend(
                extract_json_ld_events(
                    response.text,
                    source=self.name,
                    page_url=url,
                    timezone=settings.timezone,
                )
            )
            cards = _candidate_cards(response.text, url, "meetup.com")
            events.extend(
                extract_events_from_cards(
                    cards,
                    source=self.name,
                    reference_time=now,
                    timezone=settings.timezone,
                    location_hint="Singapore",
                )
            )
        return events
