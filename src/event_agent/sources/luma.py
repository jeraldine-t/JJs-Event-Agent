from __future__ import annotations

import logging
from datetime import datetime
from urllib.parse import urljoin, urlsplit

from playwright.sync_api import Page, sync_playwright

from event_agent.config import Settings
from event_agent.extraction import (
    extract_attendance_metrics,
    extract_event_from_text,
    extract_json_ld_events,
)
from event_agent.models import RawEvent
from event_agent.sources.browser_utils import parse_cookie_json

LOGGER = logging.getLogger(__name__)
PUBLIC_URL = "https://luma.com/singapore"
ACCOUNT_URL = "https://luma.com/home"
RESERVED_PATHS = {
    "",
    "about",
    "calendar",
    "create",
    "discover",
    "home",
    "login",
    "pricing",
    "signin",
    "singapore",
}


def _scroll(page: Page, rounds: int = 5) -> None:
    for _ in range(rounds):
        page.mouse.wheel(0, 4000)
        page.wait_for_timeout(500)


def _is_event_url(url: str) -> bool:
    parts = urlsplit(url)
    if (parts.hostname or "").casefold() not in {"luma.com", "www.luma.com", "lu.ma"}:
        return False
    segments = [segment.casefold() for segment in parts.path.split("/") if segment]
    if not segments or segments[0] in RESERVED_PATHS:
        return False
    return segments[0] == "event" or len(segments) == 1


class LumaSource:
    name = "Lu.ma"

    def collect(self, settings: Settings) -> list[RawEvent]:
        cookies = parse_cookie_json(settings.luma_cookies_json, default_domain=".luma.com")
        start_urls = [PUBLIC_URL, *settings.luma_private_urls]
        if cookies:
            start_urls.append(ACCOUNT_URL)
        now = datetime.now(settings.timezone)
        events: list[RawEvent] = []
        event_urls: list[str] = []
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=settings.playwright_headless)
            context = browser.new_context(locale="en-SG", timezone_id=settings.timezone_name)
            if cookies:
                context.add_cookies(cookies)
            page = context.new_page()
            for url in dict.fromkeys(start_urls):
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=60_000)
                    _scroll(page)
                    html = page.content()
                    events.extend(
                        extract_json_ld_events(
                            html,
                            source=self.name,
                            page_url=page.url,
                            timezone=settings.timezone,
                        )
                    )
                    links = page.locator("a[href]").evaluate_all("els => els.map(el => el.href)")
                    event_urls.extend(link for link in links if _is_event_url(link))
                    if _is_event_url(page.url):
                        event_urls.append(page.url)
                except Exception as exc:
                    LOGGER.warning("Lu.ma listing failed (%s)", type(exc).__name__)

            unique_urls = list(dict.fromkeys(event_urls))[: settings.luma_max_events]
            LOGGER.info("Lu.ma: inspecting %d event detail pages", len(unique_urls))
            for url in unique_urls:
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=45_000)
                    html = page.content()
                    structured = extract_json_ld_events(
                        html,
                        source=self.name,
                        page_url=page.url,
                        timezone=settings.timezone,
                    )
                    body_text = page.locator("body").inner_text(timeout=5_000)
                    metrics = extract_attendance_metrics(body_text)
                    if structured:
                        for event in structured:
                            event.metadata.update(metrics)
                            event.raw_text = body_text[:20_000]
                        events.extend(structured)
                        continue
                    event = extract_event_from_text(
                        body_text,
                        source=self.name,
                        default_url=urljoin(page.url, url),
                        reference_time=now,
                        timezone=settings.timezone,
                    )
                    if event:
                        # Without structured data there is no reliable boundary around the
                        # organizer's description, so do not present the full page as one.
                        event.description = ""
                        event.metadata.update(metrics)
                        events.append(event)
                except Exception as exc:
                    LOGGER.warning("Lu.ma event detail failed (%s)", type(exc).__name__)
            context.close()
            browser.close()
        return events
