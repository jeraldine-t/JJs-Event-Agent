from event_agent.models import canonical_url


def test_canonical_url_removes_eventbrite_affiliate_tracking() -> None:
    assert (
        canonical_url("https://www.eventbrite.sg/e/ai-night?aff=search&utm_source=weekly")
        == "https://www.eventbrite.sg/e/ai-night"
    )
