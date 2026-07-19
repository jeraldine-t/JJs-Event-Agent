from __future__ import annotations

import logging
from contextlib import ExitStack
from datetime import datetime
from urllib.parse import quote_plus, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import Page, sync_playwright

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


def _scroll_listing(page: Page, rounds: int = 5) -> None:
    for _ in range(rounds):
        page.mouse.wheel(0, 4000)
        page.wait_for_timeout(500)


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

        with ExitStack() as stack:
            playwright = None
            browser = None
            context = None
            page = None
            requests_blocked = False

            def fetch(url: str, *, listing: bool = False) -> tuple[str, str]:
                nonlocal playwright, browser, context, page, requests_blocked
                if not requests_blocked:
                    try:
                        response = session.get(url, timeout=settings.http_timeout_seconds)
                        response.raise_for_status()
                        return response.text, response.url
                    except requests.RequestException as exc:
                        requests_blocked = True
                        LOGGER.warning(
                            "Eventbrite HTTP fetch blocked (%s); switching to Chromium",
                            type(exc).__name__,
                        )

                if page is None:
                    playwright = sync_playwright().start()
                    stack.callback(playwright.stop)
                    browser = playwright.chromium.launch(
                        headless=settings.playwright_headless
                    )
                    stack.callback(browser.close)
                    context = browser.new_context(
                        locale="en-SG", timezone_id=settings.timezone_name
                    )
                    stack.callback(context.close)
                    if cookies:
                        context.add_cookies(cookies)
                    page = context.new_page()
                page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=max(settings.http_timeout_seconds * 1000, 45_000),
                )
                if listing:
                    _scroll_listing(page)
                return page.content(), page.url

            for url in self._urls(settings):
                LOGGER.info("Fetching Eventbrite public Singapore search")
                html, page_url = fetch(url, listing=True)
                listing_events = extract_json_ld_events(
                    html,
                    source=self.name,
                    page_url=page_url,
                    timezone=settings.timezone,
                )
                event_urls.extend(
                    event.url for event in listing_events if _is_event_url(event.url)
                )
                cards = _candidate_cards(html, page_url)
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
                    listing_candidates.setdefault(canonical_url(event.url), []).append(
                        event
                    )

            detail_urls = list(dict.fromkeys(canonical_url(url) for url in event_urls))[
                : settings.eventbrite_max_events
            ]
            LOGGER.info("Eventbrite: inspecting %d event detail pages", len(detail_urls))
            for url in detail_urls:
                try:
                    html, page_url = fetch(url)
                    body_text = BeautifulSoup(html, "html.parser").get_text(
                        "\n", strip=True
                    )
                    structured = extract_detail_page_events(
                        html,
                        source=self.name,
                        page_url=page_url,
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
