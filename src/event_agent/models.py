from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_QUERY_PREFIXES = ("utm_", "trk", "tracking", "ref", "source", "aff")


def canonical_url(url: str) -> str:
    """Remove fragments and common tracking parameters without changing registration tokens."""
    if not url:
        return ""
    parts = urlsplit(url.strip())
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith(TRACKING_QUERY_PREFIXES)
    ]
    path = re.sub(r"/{2,}", "/", parts.path).rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, urlencode(query), ""))


@dataclass(slots=True)
class RawEvent:
    source: str
    title: str
    description: str
    url: str
    start_at: datetime | None
    location: str
    price_text: str = ""
    end_at: datetime | None = None
    raw_text: str = ""
    discovered_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Event:
    source: str
    title: str
    description: str
    url: str
    start_at: datetime
    location: str
    keywords: tuple[str, ...]
    perks: tuple[str, ...]
    free_evidence: str
    score: int
    end_at: datetime | None = None

    @property
    def event_id(self) -> str:
        seed = f"{canonical_url(self.url)}|{self.title.casefold()}|{self.start_at.isoformat()}"
        return hashlib.sha256(seed.encode()).hexdigest()[:12]

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["id"] = self.event_id
        value["start_at"] = self.start_at.isoformat()
        value["end_at"] = self.end_at.isoformat() if self.end_at else None
        value["keywords"] = list(self.keywords)
        value["perks"] = list(self.perks)
        return value


@dataclass(slots=True)
class SourceStatus:
    source: str
    state: str
    found: int = 0
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class FilterReport:
    accepted: int = 0
    rejected: dict[str, int] = field(default_factory=dict)

    def reject(self, reason: str) -> None:
        self.rejected[reason] = self.rejected.get(reason, 0) + 1
