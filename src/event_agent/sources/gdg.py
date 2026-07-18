from __future__ import annotations

import logging
import re
from datetime import datetime
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup
from playwright.sync_api import Page, sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from event_agent.config import Settings
from event_agent.extraction import extract_event_from_text, extract_json_ld_events
from event_agent.models import RawEvent

LOGGER = logging.getLogger(__name__)
LISTING_URL = "https://gdg.community.dev/events/#/list"
SINGAPORE_CHAPTER_URL = "https://gdg.community.dev/gdg-singapore/"
FREE_REGISTRATION_RE = re.compile(
    r"\b(?:free\s+(?:registration|admission|entry|tickets?)|"
    r"(?:registration|admission|entry|tickets?)\s+(?:is|are)\s+free)\b",
    re.IGNORECASE,
)


def _is_event_url(url: str) -> bool:
    parts = urlsplit(url)
    return (
        (parts.hostname or "").casefold() == "gdg.community.dev"
        and parts.path.startswith("/events/details/")
    )


def _event_cards(page: Page) -> list[dict[str, str]]:
    return page.locator('a[href*="/events/details/"]').evaluate_all(
        """
        elements => elements.map(element => {
          const card = element.closest('li.event, article, .general-card')
            || element.parentElement
            || element;
          return {url: element.href, text: card.innerText || element.innerText || ''};
        })
        """
    )


def _registration_price_text(text: str) -> str:
    match = FREE_REGISTRATION_RE.search(text or "")
    return match.group(0) if match else ""


def parse_gdg_detail(
    html: str,
    *,
    page_url: str,
    timezone,
    listing_text: str = "",
) -> list[RawEvent]:
    """Parse a GDG detail page and preserve only explicit free-registration evidence."""
    body_text = BeautifulSoup(html, "html.parser").get_text("\n", strip=True)
    events = extract_json_ld_events(
        html,
        source="GDG",
        page_url=page_url,
        timezone=timezone,
    )
    price_text = _registration_price_text("\n".join((listing_text, body_text)))
    for event in events:
        event.price_text = price_text
        event.raw_text = body_text[:20_000]
        event.metadata["registration_signal"] = price_text
    return events


class GDGSource:
    name = "GDG"

    def collect(self, settings: Settings) -> list[RawEvent]:
        now = datetime.now(settings.timezone)
        hints: dict[str, str] = {}
        event_urls: list[str] = []
        events: list[RawEvent] = []

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=settings.playwright_headless)
            context = browser.new_context(locale="en-SG", timezone_id=settings.timezone_name)
            page = context.new_page()

            for listing_url in (LISTING_URL, SINGAPORE_CHAPTER_URL):
                try:
                    page.goto(listing_url, wait_until="domcontentloaded", timeout=60_000)
                    try:
                        page.wait_for_selector(
                            'a[href*="/events/details/"]', timeout=15_000
                        )
                    except PlaywrightTimeoutError:
                        LOGGER.warning("GDG listing rendered without event links: %s", listing_url)
                    for card in _event_cards(page):
                        url = urljoin(page.url, card.get("url", ""))
                        text = card.get("text", "")
                        if not _is_event_url(url):
                            continue
                        if listing_url == LISTING_URL and not (
                            "singapore" in text.casefold() or "gdg-singapore" in url.casefold()
                        ):
                            continue
                        normalized = url.rstrip("/")
                        event_urls.append(normalized)
                        if text:
                            hints[normalized] = text
                except Exception as exc:
                    LOGGER.warning("GDG listing failed (%s)", type(exc).__name__)

            detail_urls = list(dict.fromkeys(event_urls))[: settings.gdg_max_events]
            LOGGER.info("GDG: inspecting %d Singapore event detail pages", len(detail_urls))
            for url in detail_urls:
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=45_000)
                    html = page.content()
                    structured = parse_gdg_detail(
                        html,
                        page_url=page.url,
                        timezone=settings.timezone,
                        listing_text=hints.get(url, ""),
                    )
                    if structured:
                        events.extend(structured)
                        continue
                    body_text = page.locator("body").inner_text(timeout=5_000)
                    event = extract_event_from_text(
                        body_text,
                        source=self.name,
                        default_url=page.url,
                        reference_time=now,
                        timezone=settings.timezone,
                        location_hint="Singapore",
                    )
                    if event:
                        event.price_text = _registration_price_text(
                            "\n".join((hints.get(url, ""), body_text))
                        )
                        events.append(event)
                except Exception as exc:
                    LOGGER.warning("GDG event detail failed (%s)", type(exc).__name__)

            context.close()
            browser.close()
        return events
