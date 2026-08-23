from event_agent.config import Settings
from event_agent.sources.public_web import MeetupSource, _is_meetup_event_url


def test_meetup_detail_url_detection() -> None:
    assert _is_meetup_event_url("https://www.meetup.com/ai-singapore/events/123456789/")
    assert not _is_meetup_event_url("https://www.meetup.com/find/")
    assert not _is_meetup_event_url("https://example.com/group/events/123/")


def test_meetup_uses_separate_topic_searches_by_default(tmp_path) -> None:
    urls = MeetupSource._urls(Settings.from_env(tmp_path))

    assert len(urls) > 1
    assert any("keywords=AI" in url for url in urls)
    assert all("AI+Data+Tech" not in url for url in urls)
