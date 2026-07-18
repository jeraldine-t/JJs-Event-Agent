from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from playwright.sync_api import Locator, Page, sync_playwright

from event_agent.config import Settings
from event_agent.extraction import extract_event_from_text
from event_agent.models import RawEvent
from event_agent.sources.base import SourceNotConfigured

LOGGER = logging.getLogger(__name__)


def _search_box(page: Page) -> Locator:
    selectors = (
        '[data-testid="chat-list-search"]',
        '[contenteditable="true"][data-tab="3"]',
        '[contenteditable="true"][role="textbox"]',
    )
    for selector in selectors:
        locator = page.locator(selector).first
        if locator.count():
            return locator
    raise RuntimeError("WhatsApp search box was not found; selectors may need updating")


def _profile_exists(path: Path) -> bool:
    return path.is_dir() and any(path.iterdir())


class WhatsAppSource:
    name = "WhatsApp"

    def collect(self, settings: Settings) -> list[RawEvent]:
        if not _profile_exists(settings.whatsapp_user_data_dir):
            raise SourceNotConfigured(
                "bootstrap WHATSAPP_USER_DATA_DIR locally or use a self-hosted runner"
            )
        now = datetime.now(settings.timezone)
        events: list[RawEvent] = []
        with sync_playwright() as playwright:
            context = playwright.chromium.launch_persistent_context(
                str(settings.whatsapp_user_data_dir),
                headless=settings.playwright_headless,
                locale="en-SG",
                timezone_id=settings.timezone_name,
                viewport={"width": 1440, "height": 1000},
            )
            page = context.pages[0] if context.pages else context.new_page()
            page.goto("https://web.whatsapp.com", wait_until="domcontentloaded", timeout=90_000)
            page.wait_for_timeout(5_000)
            if page.locator('canvas[aria-label*="Scan"], [data-ref]').count():
                raise RuntimeError("WhatsApp profile is logged out; rerun the bootstrap login")

            for group in settings.whatsapp_groups:
                try:
                    search = _search_box(page)
                    search.click()
                    search.press("ControlOrMeta+A")
                    search.fill(group)
                    page.wait_for_timeout(1_500)
                    page.get_by_text(group, exact=True).last.click(timeout=15_000)
                    page.wait_for_timeout(1_500)
                    messages = page.locator(
                        '[data-testid="msg-container"], main [data-id][role="row"]'
                    )
                    count = messages.count()
                    start = max(0, count - settings.whatsapp_messages_per_group)
                    for index in range(start, count):
                        text = messages.nth(index).inner_text(timeout=3_000).strip()
                        event = extract_event_from_text(
                            text,
                            source=f"WhatsApp · {group}",
                            default_url="https://web.whatsapp.com/",
                            reference_time=now,
                            timezone=settings.timezone,
                        )
                        if event:
                            events.append(event)
                except Exception as exc:
                    LOGGER.warning("WhatsApp group failed (%s): %s", group, exc)
            context.close()
        return events

