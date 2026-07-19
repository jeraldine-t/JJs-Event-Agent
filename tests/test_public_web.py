from event_agent.sources.public_web import _is_meetup_event_url


def test_meetup_detail_url_detection() -> None:
    assert _is_meetup_event_url("https://www.meetup.com/ai-singapore/events/123456789/")
    assert not _is_meetup_event_url("https://www.meetup.com/find/")
    assert not _is_meetup_event_url("https://example.com/group/events/123/")
