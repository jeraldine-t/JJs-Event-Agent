from __future__ import annotations

import logging
from datetime import datetime
from urllib.parse import quote_plus, urlsplit

from playwright.sync_api import Page, sync_playwright

from event_agent.config import Settings
from event_agent.extraction import (
    extract_attendance_metrics,
    extract_detail_page_events,
    extract_events_from_cards,
    extract_json_ld_events,
)
from event_agent.models import RawEvent
from event_agent.sources.browser_utils import parse_cookie_json

LOGGER = logging.getLogger(__name__)


def _is_event_url(url: str) -> bool:
    parts = urlsplit(url)
    return "eventbrite." in (parts.hostname or "").casefold() and parts.path.startswith("/e/")


def _scroll(page: Page, rounds: int = 5) -> None:
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
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=settings.playwright_headless)
            context = browser.new_context(locale="en-SG", timezone_id=settings.timezone_name)
            if cookies:
                context.add_cookies(cookies)
            page = context.new_page()
            for url in self._urls(settings):
                LOGGER.info("Fetching Eventbrite search with Playwright")
                page.goto(url, wait_until="domcontentloaded", timeout=60_000)
                _scroll(page)
                events.extend(
                    extract_json_ld_events(
                        page.content(),
                        source=self.name,
                        page_url=page.url,
                        timezone=settings.timezone,
                    )
                )
                cards = page.locator('a[href*="/e/"]').evaluate_all(
                    """
                    els => els.map(el => ({
                      url: el.href,
                      text: (el.closest('article, li') || el.parentElement || el).innerText || ''
                    }))
                    """
                )
                events.extend(
                    extract_events_from_cards(
                        cards,
                        source=self.name,
                        reference_time=now,
                        timezone=settings.timezone,
                        location_hint="Singapore",
                    )
                )
                event_urls.extend(card["url"] for card in cards if _is_event_url(card["url"]))

            detail_urls = list(dict.fromkeys(event_urls))[: settings.eventbrite_max_events]
            LOGGER.info("Eventbrite: inspecting %d event detail pages", len(detail_urls))
            for url in detail_urls:
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=45_000)
                    structured = extract_detail_page_events(
                        page.content(),
                        source=self.name,
                        page_url=page.url,
                        timezone=settings.timezone,
                    )
                    body_text = page.locator("body").inner_text(timeout=5_000)
                    metrics = extract_attendance_metrics(body_text)
                    for event in structured:
                        event.metadata.update(metrics)
                        event.raw_text = body_text[:20_000]
                    events.extend(structured)
                except Exception as exc:
                    LOGGER.warning("Eventbrite detail failed (%s)", type(exc).__name__)
            context.close()
            browser.close()
        return events
