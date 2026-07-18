from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

DEFAULT_KEYWORDS = ("AI", "Tech", "Robotics", "Marketing", "Business", "Networking")
DEFAULT_WHATSAPP_GROUPS = (
    "Codex Community - Main Chat",
    "non-RWA events, programs, initiatives",
)


def _csv(value: str | None, default: tuple[str, ...] = ()) -> tuple[str, ...]:
    return tuple(item.strip() for item in (value or "").split(",") if item.strip()) or default


def _pipes(value: str | None, default: tuple[str, ...] = ()) -> tuple[str, ...]:
    return tuple(item.strip() for item in (value or "").split("|") if item.strip()) or default


def _bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().casefold() in {"1", "true", "yes", "on"}


def _int(value: str | None, default: int) -> int:
    return int(value) if value and value.strip() else default


@dataclass(frozen=True, slots=True)
class Settings:
    root: Path
    timezone_name: str
    keywords: tuple[str, ...]
    lookahead_days: int
    message_lookback_days: int
    playwright_headless: bool
    enabled_sources: tuple[str, ...]
    output_html: Path
    source_failure_mode: str
    http_timeout_seconds: int
    linkedin_li_at: str
    linkedin_cookies_json: str
    linkedin_max_profiles: int
    linkedin_posts_per_profile: int
    eventbrite_cookies_json: str
    eventbrite_max_events: int
    gdg_max_events: int
    luma_cookies_json: str
    luma_private_urls: tuple[str, ...]
    luma_max_events: int
    whatsapp_user_data_dir: Path
    whatsapp_groups: tuple[str, ...]
    whatsapp_messages_per_group: int
    eventbrite_search_urls: tuple[str, ...]
    meetup_search_urls: tuple[str, ...]
    email_enabled: bool
    email_recipient: str
    smtp_host: str
    smtp_port: int
    smtp_security: str
    smtp_username: str
    smtp_password: str
    smtp_from: str

    @property
    def timezone(self) -> ZoneInfo:
        return ZoneInfo(self.timezone_name)

    @classmethod
    def from_env(cls, root: Path | None = None) -> Settings:
        root = (root or Path.cwd()).resolve()
        load_dotenv(root / ".env")
        output = Path(os.getenv("OUTPUT_HTML", "index.html"))
        whatsapp_dir = Path(os.getenv("WHATSAPP_USER_DATA_DIR") or ".state/whatsapp")
        return cls(
            root=root,
            timezone_name=os.getenv("TIMEZONE", "Asia/Singapore"),
            keywords=_csv(os.getenv("EVENT_KEYWORDS"), DEFAULT_KEYWORDS),
            lookahead_days=_int(os.getenv("LOOKAHEAD_DAYS"), 90),
            message_lookback_days=_int(os.getenv("MESSAGE_LOOKBACK_DAYS"), 14),
            playwright_headless=_bool(os.getenv("PLAYWRIGHT_HEADLESS"), True),
            enabled_sources=_csv(
                os.getenv("ENABLED_SOURCES"),
                ("linkedin", "eventbrite", "luma", "meetup", "gdg"),
            ),
            output_html=output if output.is_absolute() else root / output,
            source_failure_mode=os.getenv("SOURCE_FAILURE_MODE", "warn").casefold(),
            http_timeout_seconds=_int(os.getenv("HTTP_TIMEOUT_SECONDS"), 30),
            linkedin_li_at=os.getenv("LINKEDIN_LI_AT", "").strip(),
            linkedin_cookies_json=os.getenv("LINKEDIN_COOKIES_JSON", "").strip(),
            linkedin_max_profiles=_int(os.getenv("LINKEDIN_MAX_PROFILES"), 30),
            linkedin_posts_per_profile=_int(os.getenv("LINKEDIN_POSTS_PER_PROFILE"), 12),
            eventbrite_cookies_json=os.getenv("EVENTBRITE_COOKIES_JSON", "").strip(),
            eventbrite_max_events=_int(os.getenv("EVENTBRITE_MAX_EVENTS"), 80),
            gdg_max_events=_int(os.getenv("GDG_MAX_EVENTS"), 60),
            luma_cookies_json=os.getenv("LUMA_COOKIES_JSON", "").strip(),
            luma_private_urls=_csv(os.getenv("LUMA_PRIVATE_URLS")),
            luma_max_events=_int(os.getenv("LUMA_MAX_EVENTS"), 80),
            whatsapp_user_data_dir=(
                whatsapp_dir if whatsapp_dir.is_absolute() else root / whatsapp_dir
            ),
            whatsapp_groups=_pipes(os.getenv("WHATSAPP_GROUPS"), DEFAULT_WHATSAPP_GROUPS),
            whatsapp_messages_per_group=_int(os.getenv("WHATSAPP_MESSAGES_PER_GROUP"), 100),
            eventbrite_search_urls=_pipes(os.getenv("EVENTBRITE_SEARCH_URLS")),
            meetup_search_urls=_pipes(os.getenv("MEETUP_SEARCH_URLS")),
            email_enabled=_bool(os.getenv("EMAIL_ENABLED"), False),
            email_recipient=os.getenv(
                "EMAIL_RECIPIENT", "jeraldine.openai@outlook.com"
            ).strip(),
            smtp_host=os.getenv("SMTP_HOST", "").strip(),
            smtp_port=_int(os.getenv("SMTP_PORT"), 587),
            smtp_security=(os.getenv("SMTP_SECURITY") or "starttls").strip().casefold(),
            smtp_username=os.getenv("SMTP_USERNAME", "").strip(),
            smtp_password=os.getenv("SMTP_PASSWORD", ""),
            smtp_from=os.getenv("SMTP_FROM", "").strip(),
        )
