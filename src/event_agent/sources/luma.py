from __future__ import annotations

import logging
from datetime import datetime
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from event_agent.config import Settings
from event_agent.extraction import (
    extract_attendance_metrics,
    extract_detail_page_events,
    extract_event_from_text,
    extract_event_overview,
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
        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131 Safari/537.36"
                ),
                "Accept-Language": "en-SG,en;q=0.9",
            }
        )
        for cookie in cookies:
            session.cookies.set(
                cookie["name"],
                cookie["value"],
                domain=cookie.get("domain") or ".luma.com",
                path=cookie.get("path") or "/",
            )

        for url in dict.fromkeys(start_urls):
            try:
                response = session.get(url, timeout=settings.http_timeout_seconds)
                response.raise_for_status()
                if _is_event_url(response.url):
                    event_urls.append(response.url)
                    continue
                listing_events = extract_json_ld_events(
                    response.text,
                    source=self.name,
                    page_url=response.url,
                    timezone=settings.timezone,
                )
                event_urls.extend(
                    event.url for event in listing_events if _is_event_url(event.url)
                )
                soup = BeautifulSoup(response.text, "html.parser")
                event_urls.extend(
                    urljoin(response.url, str(anchor.get("href", "")))
                    for anchor in soup.select("a[href]")
                    if _is_event_url(
                        urljoin(response.url, str(anchor.get("href", "")))
                    )
                )
            except Exception as exc:
                LOGGER.warning("Lu.ma listing failed (%s)", type(exc).__name__)

        unique_urls = list(dict.fromkeys(event_urls))[: settings.luma_max_events]
        LOGGER.info("Lu.ma: inspecting %d event detail pages", len(unique_urls))
        for url in unique_urls:
            try:
                response = session.get(url, timeout=settings.http_timeout_seconds)
                response.raise_for_status()
                html = response.text
                structured = extract_detail_page_events(
                    html,
                    source=self.name,
                    page_url=response.url,
                    timezone=settings.timezone,
                )
                body_text = BeautifulSoup(html, "html.parser").get_text("\n", strip=True)
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
                    default_url=urljoin(response.url, url),
                    reference_time=now,
                    timezone=settings.timezone,
                )
                if event:
                    event.description = extract_event_overview(html)
                    event.metadata["overview_source"] = "event-detail-page"
                    event.metadata.update(metrics)
                    events.append(event)
            except Exception as exc:
                LOGGER.warning("Lu.ma event detail failed (%s)", type(exc).__name__)
        return events
