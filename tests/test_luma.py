from event_agent.sources.luma import PUBLIC_URL, _is_event_url


def test_luma_singapore_is_the_public_discovery_source() -> None:
    assert PUBLIC_URL == "https://luma.com/singapore"


def test_luma_event_url_detection() -> None:
    assert _is_event_url("https://luma.com/daytonasg")
    assert _is_event_url("https://lu.ma/event/abc123")
    assert not _is_event_url("https://luma.com/singapore")
