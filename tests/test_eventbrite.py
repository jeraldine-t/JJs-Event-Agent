from event_agent.sources.eventbrite import _is_event_url


def test_eventbrite_event_url_detection() -> None:
    assert _is_event_url("https://www.eventbrite.sg/e/ai-night-tickets-12345")
    assert _is_event_url("https://www.eventbrite.com/e/robotics-meetup-tickets-67890")
    assert not _is_event_url("https://www.eventbrite.sg/d/singapore/free--events/")
    assert not _is_event_url("https://example.com/e/not-eventbrite")
