from requests.cookies import RequestsCookieJar

from event_agent.config import Settings
from event_agent.sources import eventbrite
from event_agent.sources.eventbrite import EventbriteSource, _is_event_url


def test_eventbrite_event_url_detection() -> None:
    assert _is_event_url("https://www.eventbrite.sg/e/ai-night-tickets-12345")
    assert _is_event_url("https://www.eventbrite.com/e/robotics-meetup-tickets-67890")
    assert not _is_event_url("https://www.eventbrite.sg/d/singapore/free--events/")
    assert not _is_event_url("https://example.com/e/not-eventbrite")


def test_eventbrite_enriches_recurring_listing_date_with_detail_overview(
    tmp_path, monkeypatch
) -> None:
    detail_url = "https://www.eventbrite.sg/e/ai-networking-tickets-12345"
    listing_html = f"""
    <ul><li><a href="{detail_url}"></a>
      <h3>AI Networking Singapore</h3>
      <div>Thu, Aug 6 • 7:00 PM</div><div>Singapore · Downtown Core</div><div>Free</div>
    </li></ul>
    """
    detail_html = f"""
    <script type="application/ld+json">
    {{"@context":"https://schema.org","@type":"SocialEvent",
     "name":"AI Networking Singapore","description":"Meet AI builders and founders.",
     "startDate":"2025-02-06T19:00:00+08:00","endDate":"2028-01-06T21:00:00+08:00",
     "location":{{"@type":"Place","name":"Downtown Core",
       "address":{{"addressLocality":"Singapore"}}}},
     "offers":{{"price":0,"priceCurrency":"SGD"}},"url":"{detail_url}"}}
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
            if "/d/" in url:
                return FakeResponse(url, listing_html)
            return FakeResponse(url, detail_html)

    monkeypatch.setattr(eventbrite.requests, "Session", FakeSession)
    events = EventbriteSource().collect(Settings.from_env(tmp_path))
    recurring = next(event for event in events if event.start_at.year == 2026)
    assert recurring.title == "AI Networking Singapore"
    assert recurring.description == "Meet AI builders and founders."
    assert recurring.metadata["overview_source"] == "event-detail-page"
