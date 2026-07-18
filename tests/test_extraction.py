from datetime import datetime
from zoneinfo import ZoneInfo

from event_agent.extraction import extract_json_ld_events

SGT = ZoneInfo("Asia/Singapore")


def test_extracts_schema_event() -> None:
    html = """
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "Event",
      "name": "AI Founder Night",
      "description": "Free admission with pizza and networking",
      "startDate": "2026-07-20T19:00:00+08:00",
      "location": {
        "@type": "Place",
        "name": "LaunchPad",
        "address": {"addressLocality": "Singapore", "postalCode": "138602"}
      },
      "offers": {"price": 0, "priceCurrency": "SGD"},
      "url": "/ai-night"
    }
    </script>
    """
    events = extract_json_ld_events(
        html, source="Fixture", page_url="https://events.example/", timezone=SGT
    )
    assert len(events) == 1
    assert events[0].title == "AI Founder Night"
    assert events[0].start_at == datetime(2026, 7, 20, 19, 0, tzinfo=SGT)
    assert events[0].location == "LaunchPad, Singapore, 138602"
    assert events[0].price_text == "SGD 0"
    assert events[0].url == "https://events.example/ai-night"

