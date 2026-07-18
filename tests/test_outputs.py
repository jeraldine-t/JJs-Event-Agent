from datetime import datetime
from zoneinfo import ZoneInfo

from event_agent.models import Event, FilterReport, SourceStatus
from event_agent.outputs.dashboard import render_dashboard
from event_agent.outputs.telegram_bot import _chunks

SGT = ZoneInfo("Asia/Singapore")


def event() -> Event:
    return Event(
        source="Lu.ma",
        title="AI & <Robotics> Night",
        description="Private source material must not be published verbatim.",
        url="https://lu.ma/example",
        start_at=datetime(2026, 7, 20, 19, 0, tzinfo=SGT),
        location="Singapore",
        keywords=("AI", "Robotics", "Networking"),
        perks=("Pizza", "Networking"),
        free_evidence="Free admission",
        score=49,
    )


def test_dashboard_is_self_contained_and_does_not_publish_description(tmp_path) -> None:
    output = tmp_path / "index.html"
    render_dashboard(
        [event()],
        [SourceStatus("Lu.ma", "ok", found=1)],
        FilterReport(accepted=1),
        generated_at=datetime(2026, 7, 18, 8, 0, tzinfo=SGT),
        output_path=output,
    )
    html = output.read_text()
    assert "AI &amp; &lt;Robotics&gt; Night" in html
    assert "Private source material" not in html
    assert html.count(">Networking<") == 1
    assert "<style>" in html and "<script>" in html


def test_telegram_html_is_escaped() -> None:
    message = _chunks([event()])[0]
    assert "AI &amp; &lt;Robotics&gt; Night" in message
    assert "https://lu.ma/example" in message
