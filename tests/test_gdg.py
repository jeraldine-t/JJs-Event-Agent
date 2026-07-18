from zoneinfo import ZoneInfo

from event_agent.sources.gdg import _is_event_url, parse_gdg_detail

SGT = ZoneInfo("Asia/Singapore")


def test_gdg_detail_uses_schema_and_explicit_free_registration() -> None:
    html = """
    <html><body><p>Free registration</p>
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "Event",
      "name": "AI Builders Night",
      "startDate": "2026-08-04T18:30:00+08:00",
      "description": "Build useful AI agents with Google technology.",
      "location": {
        "@type": "Place",
        "name": "Developer Space",
        "address": {"addressLocality": "Singapore", "addressCountry": "SG"}
      }
    }
    </script></body></html>
    """
    events = parse_gdg_detail(
        html,
        page_url="https://gdg.community.dev/events/details/example/",
        timezone=SGT,
    )
    assert len(events) == 1
    assert events[0].source == "GDG"
    assert events[0].price_text.casefold() == "free registration"
    assert events[0].location == "Developer Space, Singapore, SG"


def test_gdg_external_registration_is_not_assumed_free() -> None:
    html = """
    <script type="application/ld+json">
    {"@context":"https://schema.org","@type":"Event","name":"Tech Night",
     "startDate":"2026-08-04T18:30:00+08:00","location":"Singapore"}
    </script>
    """
    events = parse_gdg_detail(
        html,
        page_url="https://gdg.community.dev/events/details/example/",
        timezone=SGT,
        listing_text="External registration",
    )
    assert events[0].price_text == ""


def test_gdg_event_url_validation() -> None:
    assert _is_event_url("https://gdg.community.dev/events/details/example/")
    assert not _is_event_url("https://gdg.community.dev/gdg-singapore/")
    assert not _is_event_url("https://example.com/events/details/example/")
