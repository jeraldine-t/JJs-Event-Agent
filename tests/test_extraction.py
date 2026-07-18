from datetime import datetime
from zoneinfo import ZoneInfo

from event_agent.extraction import extract_event_from_text, extract_json_ld_events

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


def test_card_date_separator_preserves_time_and_clean_fields() -> None:
    event = extract_event_from_text(
        "Business Networking Singapore (Free Entry)\n"
        "Thu, Aug 20 • 7:00 PM + 17 more\n"
        "Singapore · Rocky Master\n"
        "Free",
        source="Eventbrite",
        default_url="https://example.com/event",
        reference_time=datetime(2026, 7, 18, 12, 0, tzinfo=SGT),
        timezone=SGT,
    )
    assert event is not None
    assert event.start_at == datetime(2026, 8, 20, 19, 0, tzinfo=SGT)
    assert event.location == "Singapore · Rocky Master"
    assert event.price_text == "Free"


def test_relative_weekday_card_keeps_afternoon_time() -> None:
    event = extract_event_from_text(
        "AI workshop\nWednesday • 2:30 PM\nSingapore\nFree",
        source="Eventbrite",
        default_url="https://example.com/event",
        reference_time=datetime(2026, 7, 18, 12, 0, tzinfo=SGT),
        timezone=SGT,
    )
    assert event is not None
    assert event.start_at == datetime(2026, 7, 22, 14, 30, tzinfo=SGT)
