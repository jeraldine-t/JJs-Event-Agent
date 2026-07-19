from datetime import datetime
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from event_agent.models import Event, FilterReport, SourceStatus
from event_agent.outputs.dashboard import render_dashboard

SGT = ZoneInfo("Asia/Singapore")


def event(*, source: str = "LinkedIn", description: str = "Organizer event overview") -> Event:
    return Event(
        source=source,
        title="AI & <Robotics> Night",
        description=description,
        url="https://example.com/event",
        start_at=datetime(2026, 7, 20, 19, 0, tzinfo=SGT),
        location="Singapore",
        keywords=("AI", "Robotics", "Networking"),
        perks=("Pizza", "Networking"),
        free_evidence="Free admission",
        score=49,
    )


def render(tmp_path, events: list[Event]) -> str:
    output = tmp_path / "index.html"
    render_dashboard(
        events,
        [SourceStatus(events[0].source, "ok", found=len(events))],
        FilterReport(accepted=len(events)),
        generated_at=datetime(2026, 7, 18, 8, 0, tzinfo=SGT),
        output_path=output,
    )
    return output.read_text()


def test_dashboard_is_self_contained_and_calendar_is_open_ended(tmp_path) -> None:
    html = render(tmp_path, [event(description="Organizer overview for the event.")])
    assert "AI &amp; &lt;Robotics&gt; Night" in html
    assert "Organizer overview for the event." in html
    assert html.count(">Networking<") == 1
    assert "Food &amp; beverage" in html
    assert "Pizza" in html
    assert '<option value="pizza">Pizza</option>' in html
    assert '<option value="dinner">Dinner</option>' in html
    assert 'data-fnb-types="pizza"' in html
    assert '<option value="lu.ma">Lu.ma · Singapore</option>' in html
    assert "18 Jul 2026 · 8:00 AM SGT" in html
    assert "JJ's Event Agent" in html
    assert 'class="calendar-overview"' in html
    assert 'id="month-grid"' in html
    assert "moveMonth(-1)" in html
    assert "moveMonth(1)" in html
    assert "previousMonth.disabled" not in html
    assert "<style>" in html and "<script>" in html


def test_public_summary_is_strictly_less_than_100_words(tmp_path) -> None:
    description = " ".join(f"word{number}" for number in range(130))
    html = render(tmp_path, [event(source="GDG", description=description)])
    soup = BeautifulSoup(html, "html.parser")
    summary = soup.select_one(".summary")
    assert summary is not None
    assert len(summary.get_text(" ", strip=True).split()) == 99
    assert "word129" not in summary.get_text()


def test_summary_uses_event_overview_only_without_inferred_copy(tmp_path) -> None:
    described = event(source="Eventbrite", description="Organizer-written overview only.")
    html = render(tmp_path, [described])
    assert "Organizer-written overview only." in html
    assert "curated Singapore timing window" not in html
    assert "event description was provided" not in html


def test_dashboard_marks_fnb_as_not_stated(tmp_path) -> None:
    without_fnb = event(source="Eventbrite", description="A concise public summary.")
    without_fnb.perks = ("Networking",)
    html = render(tmp_path, [without_fnb])
    assert 'data-fnb-types="not-stated"' in html
    assert "Not stated" in html


def test_dashboard_shows_signup_interest_and_hot_pick(tmp_path) -> None:
    popular = event(source="Lu.ma", description="A public AI builders event.")
    popular.attendee_count = 200
    popular.seats_left = 0
    popular.registration_status = "waitlist"
    html = render(tmp_path, [popular])
    assert "Hot pick" in html
    assert "200 going" in html
    assert "Waitlist / full" in html
