from __future__ import annotations

import logging
from datetime import datetime
from urllib.parse import urljoin, urlsplit, urlunsplit

from playwright.sync_api import Page, sync_playwright

from event_agent.config import Settings
from event_agent.extraction import extract_detail_page_events, extract_event_from_text
from event_agent.models import RawEvent
from event_agent.sources.base import SourceNotConfigured
from event_agent.sources.browser_utils import parse_cookie_json

LOGGER = logging.getLogger(__name__)
FOLLOWING_URL = "https://www.linkedin.com/mynetwork/network-manager/people-follow/following/"
EVENT_DETAIL_HOSTS = (
    "eventbrite.com",
    "eventbrite.sg",
    "gdg.community.dev",
    "lu.ma",
    "luma.com",
    "meetup.com",
)


def _profile_url(href: str) -> str:
    full = urljoin("https://www.linkedin.com", href)
    parts = urlsplit(full)
    return urlunsplit(("https", "www.linkedin.com", parts.path.rstrip("/"), "", ""))


def _scroll(page: Page, rounds: int = 5) -> None:
    for _ in range(rounds):
        page.mouse.wheel(0, 4000)
        page.wait_for_timeout(600)


def _event_detail_url(links: list[str]) -> str:
    for link in links:
        hostname = (urlsplit(link).hostname or "").casefold()
        if any(hostname == host or hostname.endswith(f".{host}") for host in EVENT_DETAIL_HOSTS):
            return link
    return ""


class LinkedInSource:
    name = "LinkedIn"

    def collect(self, settings: Settings) -> list[RawEvent]:
        if not settings.linkedin_li_at and not settings.linkedin_cookies_json:
            raise SourceNotConfigured("set LINKEDIN_LI_AT or LINKEDIN_COOKIES_JSON")

        cookies = parse_cookie_json(
            settings.linkedin_cookies_json, default_domain=".linkedin.com"
        )
        if settings.linkedin_li_at:
            cookies.append(
                {
                    "name": "li_at",
                    "value": settings.linkedin_li_at,
                    "domain": ".linkedin.com",
                    "path": "/",
                    "secure": True,
                    "httpOnly": True,
                }
            )
        now = datetime.now(settings.timezone)
        events: list[RawEvent] = []
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=settings.playwright_headless)
            context = browser.new_context(locale="en-SG", timezone_id=settings.timezone_name)
            context.add_cookies(cookies)
            page = context.new_page()
            page.goto(FOLLOWING_URL, wait_until="domcontentloaded", timeout=60_000)
            if "/login" in page.url or "/checkpoint" in page.url:
                raise RuntimeError("LinkedIn session was rejected or requires a checkpoint")
            detail_page = context.new_page()
            _scroll(page)
            profile_links = page.locator('a[href*="/in/"]').evaluate_all(
                "els => els.map(el => el.href)"
            )
            profiles = list(
                dict.fromkeys(_profile_url(url) for url in profile_links if "/in/" in url)
            )[: settings.linkedin_max_profiles]
            LOGGER.info("LinkedIn: checking recent posts from %d followed profiles", len(profiles))
            for profile in profiles:
                activity_url = f"{profile}/recent-activity/all/"
                try:
                    page.goto(
                        activity_url, wait_until="domcontentloaded", timeout=45_000
                    )
                    _scroll(page, rounds=2)
                    posts = page.locator(
                        ".feed-shared-update-v2, article, .occludable-update"
                    )
                    for index in range(min(posts.count(), settings.linkedin_posts_per_profile)):
                        post = posts.nth(index)
                        text = post.inner_text(timeout=5_000).strip()
                        links = post.locator("a[href]").evaluate_all(
                            "els => els.map(el => el.href)"
                        )
                        default_url = next(
                            (url for url in links if "/feed/update/" in url), activity_url
                        )
                        event = extract_event_from_text(
                            text,
                            source=self.name,
                            default_url=default_url,
                            reference_time=now,
                            timezone=settings.timezone,
                        )
                        if event:
                            # The LinkedIn post helps discover the event, but its private
                            # body is never used as the public dashboard overview.
                            event.description = ""
                            detail_url = _event_detail_url(links)
                            if detail_url:
                                try:
                                    detail_page.goto(
                                        detail_url,
                                        wait_until="domcontentloaded",
                                        timeout=45_000,
                                    )
                                    structured = extract_detail_page_events(
                                        detail_page.content(),
                                        source=self.name,
                                        page_url=detail_page.url,
                                        timezone=settings.timezone,
                                    )
                                    if structured:
                                        detail = max(
                                            structured,
                                            key=lambda candidate: len(candidate.description),
                                        )
                                        detail.raw_text = event.raw_text
                                        detail.metadata["discovered_via"] = "linkedin"
                                        events.append(detail)
                                        continue
                                except Exception as exc:
                                    LOGGER.warning(
                                        "LinkedIn event overview failed (%s)",
                                        type(exc).__name__,
                                    )
                            events.append(event)
                except Exception as exc:  # one profile must not abort the network scan
                    LOGGER.warning("LinkedIn profile failed (%s): %s", profile, exc)
            context.close()
            browser.close()
        return events
