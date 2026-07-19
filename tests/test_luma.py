from requests.cookies import RequestsCookieJar

from event_agent.config import Settings
from event_agent.sources import luma
from event_agent.sources.luma import (
    CURATED_DISCOVERY_URLS,
    PUBLIC_URL,
    LumaSource,
    _is_event_url,
)


def test_luma_singapore_is_the_public_discovery_source() -> None:
    assert PUBLIC_URL == "https://luma.com/singapore"


def test_luma_event_url_detection() -> None:
    assert _is_event_url("https://luma.com/daytonasg")
    assert _is_event_url("https://lu.ma/event/abc123")
    assert not _is_event_url("https://luma.com/singapore")
    assert not _is_event_url(CURATED_DISCOVERY_URLS[0])


def test_luma_follows_listing_event_to_detail_overview(tmp_path, monkeypatch) -> None:
    listing_html = """
    <script type="application/ld+json">
    {"@context":"https://schema.org","@type":"Event","name":"AI Builders",
     "startDate":"2026-07-22T18:30:00+08:00","location":"Singapore",
     "url":"https://luma.com/abc"}
    </script>
    """
    detail_html = """
    <script type="application/ld+json">
    {"@context":"https://schema.org","@type":"Event","name":"AI Builders",
     "description":"Organizer overview for AI builders in Singapore.",
     "startDate":"2026-07-22T18:30:00+08:00","location":"Singapore",
     "url":"https://luma.com/abc"}
    </script>
    """

    class FakeResponse:
        def __init__(self, url, text):
            self.url = url
            self.text = text

        def raise_for_status(self):
            return None

    class FakeSession:
        def __init__(self):
            self.headers = {}
            self.cookies = RequestsCookieJar()

        def get(self, url, timeout):
            assert timeout > 0
            if url == PUBLIC_URL:
                return FakeResponse(url, listing_html)
            return FakeResponse(url, detail_html)

    monkeypatch.setattr(luma.requests, "Session", FakeSession)
    settings = Settings.from_env(tmp_path)
    events = LumaSource().collect(settings)
    assert len(events) == 1
    assert events[0].description == "Organizer overview for AI builders in Singapore."


def test_luma_follows_curated_calendar_to_singapore_event(tmp_path, monkeypatch) -> None:
    calendar_html = '<a href="/clickh-2r4t">ClickHouse Singapore</a>'
    detail_html = """
    <script type="application/ld+json">
    {"@context":"https://schema.org","@type":"Event",
     "name":"ClickHouse Singapore August 2026 Edition",
     "description":"Database experts, developer tools, dinner and networking.",
     "startDate":"2026-08-04T18:00:00+08:00",
     "location":{"@type":"Place","name":"IMDA",
       "address":{"streetAddress":"10 Pasir Panjang Rd, Mapletree Business City",
       "addressLocality":"Singapore","addressCountry":"SG"}},
     "offers":{"@type":"Offer","price":0,"priceCurrency":"SGD"},
     "url":"https://luma.com/clickh-2r4t"}
    </script>
    """

    class FakeResponse:
        def __init__(self, url, text):
            self.url = url
            self.text = text

        def raise_for_status(self):
            return None

    class FakeSession:
        def __init__(self):
            self.headers = {}
            self.cookies = RequestsCookieJar()

        def get(self, url, timeout):
            assert timeout > 0
            if url == "https://luma.com/clickh-2r4t":
                return FakeResponse(url, detail_html)
            return FakeResponse(url, calendar_html if url in CURATED_DISCOVERY_URLS else "")

    monkeypatch.setattr(luma.requests, "Session", FakeSession)
    settings = Settings.from_env(tmp_path)
    events = LumaSource().collect(settings)
    assert [event.title for event in events] == [
        "ClickHouse Singapore August 2026 Edition"
    ]
    assert events[0].metadata["structured_price"] == 0
