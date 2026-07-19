from datetime import datetime
from zoneinfo import ZoneInfo

from event_agent.extraction import (
    extract_attendance_metrics,
    extract_detail_page_events,
    extract_event_from_text,
    extract_event_overview,
    extract_events_from_cards,
    extract_json_ld_events,
)

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
    assert events[0].metadata["structured_price"] == 0
    assert events[0].url == "https://events.example/ai-night"


def test_extracts_schema_event_subtype() -> None:
    html = """
    <script type="application/ld+json">
    {"@context":"https://schema.org","@type":"SocialEvent","name":"AI Social",
     "description":"An organizer overview for an AI networking evening.",
     "startDate":"2026-07-20T19:00:00+08:00","location":"Singapore"}
    </script>
    """
    events = extract_json_ld_events(
        html, source="Eventbrite", page_url="https://example.com/event", timezone=SGT
    )
    assert len(events) == 1
    assert events[0].title == "AI Social"


def test_extracts_luma_style_about_event_overview() -> None:
    html = """
    <section class="event-about-card">
      <div>About Event</div>
      <div><p>Build useful AI agents with experienced Singapore engineers.</p></div>
    </section>
    """
    assert extract_event_overview(html) == (
        "Build useful AI agents with experienced Singapore engineers."
    )


def test_detail_page_fills_missing_json_ld_description_from_overview() -> None:
    html = """
    <script type="application/ld+json">
    {"@context":"https://schema.org","@type":"Event","name":"AI Night",
     "startDate":"2026-07-20T19:00:00+08:00","location":"Singapore"}
    </script>
    <section class="event-about-card">
      <div>About Event</div>
      <div>Learn to build production AI agents with a Singapore community.</div>
    </section>
    """
    event = extract_detail_page_events(
        html, source="Lu.ma", page_url="https://luma.com/abc", timezone=SGT
    )[0]
    assert event.description == (
        "Learn to build production AI agents with a Singapore community."
    )
    assert event.metadata["overview_source"] == "event-detail-page"


def test_detail_page_prefers_full_details_section_over_schema_excerpt() -> None:
    html = """
    <script type="application/ld+json">
    {"@context":"https://schema.org","@type":"Event","name":"AI Night",
     "description":"A shortened schema excerpt.",
     "startDate":"2026-07-20T19:00:00+08:00","location":"Singapore"}
    </script>
    <section>
      <div><h2>Details</h2></div>
      <div>Build practical AI products with Singapore founders and engineers.
      The organizer will walk through real examples and implementation choices.</div>
    </section>
    """
    event = extract_detail_page_events(
        html, source="Meetup", page_url="https://meetup.com/group/events/123", timezone=SGT
    )[0]
    assert event.description.startswith("Build practical AI products")
    assert "implementation choices" in event.description


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


def test_listing_card_ui_text_is_not_used_as_an_event_description() -> None:
    events = extract_events_from_cards(
        [
            {
                "text": "AI builders night\nTue, Jul 21 • 7:00 PM\nSingapore\nFree",
                "url": "https://example.com/event",
            }
        ],
        source="Eventbrite",
        reference_time=datetime(2026, 7, 18, 12, 0, tzinfo=SGT),
        timezone=SGT,
    )

    assert events[0].description == ""
    assert "AI builders night" in events[0].raw_text


def test_extracts_luma_style_attendance_and_waitlist() -> None:
    metrics = extract_attendance_metrics("284 Going Event Full Join the Waiting List")
    assert metrics == {
        "attendee_count": 284,
        "registration_status": "waitlist",
        "seats_left": 0,
    }


def test_extracts_seats_left_and_capacity() -> None:
    metrics = extract_attendance_metrics("Only 8 seats left. Event capacity: 120")
    assert metrics == {"seats_left": 8, "capacity": 120}


def test_json_ld_capacity_becomes_signup_metrics() -> None:
    html = """
    <script type="application/ld+json">
    {"@context":"https://schema.org","@type":"Event","name":"AI Night",
     "startDate":"2026-07-20T19:00:00+08:00","location":"Singapore",
     "maximumAttendeeCapacity":100,"remainingAttendeeCapacity":12}
    </script>
    """
    event = extract_json_ld_events(
        html, source="Fixture", page_url="https://example.com/event", timezone=SGT
    )[0]
    assert event.metadata["capacity"] == 100
    assert event.metadata["seats_left"] == 12
    assert event.metadata["attendee_count"] == 88
