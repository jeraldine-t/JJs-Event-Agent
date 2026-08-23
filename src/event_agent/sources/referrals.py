"""Privacy-safe ingestion of public event URLs discovered in local private sources."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from urllib.parse import urlsplit

import requests
from bs4 import BeautifulSoup

from event_agent.config import Settings
from event_agent.extraction import extract_attendance_metrics, extract_detail_page_events
from event_agent.models import RawEvent
from event_agent.sources.base import SourceNotConfigured

LOGGER = logging.getLogger(__name__)


def _public_urls(queue_path: Path) -> list[str]:
    """Load only URLs from a local queue; chat content is intentionally unsupported."""
    try:
        payload = json.loads(queue_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SourceNotConfigured("local public-referral queue is unavailable") from exc

    values = payload.get("urls", []) if isinstance(payload, dict) else payload
    urls: list[str] = []
    for value in values if isinstance(values, list) else []:
        url = value.get("url", "") if isinstance(value, dict) else value
        parts = urlsplit(str(url).strip())
        if parts.scheme in {"http", "https"} and parts.netloc:
            urls.append(str(url).strip())
    return list(dict.fromkeys(urls))


class PublicReferralSource:
    """Verify public detail pages reached through a local Telegram or WhatsApp queue."""

    def __init__(self, name: str, queue_path: Path) -> None:
        self.name = name
        self.queue_path = queue_path

    def collect(self, settings: Settings) -> list[RawEvent]:
        if not self.queue_path.is_file():
            raise SourceNotConfigured("local public-referral queue is not configured")

        events: list[RawEvent] = []
        session = requests.Session()
        session.headers["User-Agent"] = "JJ's Event Agent public page verifier"
        for url in _public_urls(self.queue_path):
            try:
                # No cookies are ever supplied here: a page must stand on its own publicly.
                response = session.get(url, timeout=settings.http_timeout_seconds)
                response.raise_for_status()
                html = response.text
                page_events = extract_detail_page_events(
                    html,
                    source=self.name,
                    page_url=response.url,
                    timezone=settings.timezone,
                )
                public_text = BeautifulSoup(html, "html.parser").get_text("\n", strip=True)
                metrics = extract_attendance_metrics(public_text)
                for event in page_events:
                    event.metadata.update(metrics)
                    event.raw_text = public_text[:20_000]
                events.extend(page_events)
            except Exception as exc:
                LOGGER.info("%s public URL skipped (%s)", self.name, type(exc).__name__)
        return events
