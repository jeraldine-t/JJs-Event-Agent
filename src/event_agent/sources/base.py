from __future__ import annotations

from typing import Protocol

from event_agent.config import Settings
from event_agent.models import RawEvent


class SourceNotConfigured(RuntimeError):
    """Raised when a source cannot run until its account credentials are configured."""


class EventSource(Protocol):
    name: str

    def collect(self, settings: Settings) -> list[RawEvent]: ...

