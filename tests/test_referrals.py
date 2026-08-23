import json

from event_agent.config import Settings
from event_agent.sources import referrals
from event_agent.sources.referrals import PublicReferralSource


def test_public_referral_source_reads_urls_only_and_verifies_detail_pages(
    tmp_path, monkeypatch
) -> None:
    event_url = "https://events.example/ai-night"
    queue = tmp_path / "telegram-referrals.json"
    queue.write_text(json.dumps({"urls": [event_url, "not-a-url"]}), encoding="utf-8")
    detail_html = f"""
    <script type="application/ld+json">
    {{"@context":"https://schema.org","@type":"Event","name":"AI Builders Night",
    "description":"An organizer overview for Singapore AI builders.",
    "startDate":"2026-09-03T19:00:00+08:00",
    "location":{{"@type":"Place","name":"One-North",
    "address":{{"addressLocality":"Singapore"}}}},"url":"{event_url}"}}
    </script>
    <p>Public organizer overview</p>
    """

    class FakeResponse:
        url = event_url
        text = detail_html

        @staticmethod
        def raise_for_status():
            return None

    class FakeSession:
        def __init__(self):
            self.headers = {}

        @staticmethod
        def get(url, timeout):
            assert url == event_url
            assert timeout > 0
            return FakeResponse()

    monkeypatch.setattr(referrals.requests, "Session", FakeSession)
    events = PublicReferralSource("Telegram · verified public page", queue).collect(
        Settings.from_env(tmp_path)
    )

    assert len(events) == 1
    assert events[0].source == "Telegram · verified public page"
    assert events[0].metadata["overview_source"] == "event-detail-page"
    assert "Public organizer overview" in events[0].raw_text
