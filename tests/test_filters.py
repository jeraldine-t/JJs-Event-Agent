from datetime import datetime
from zoneinfo import ZoneInfo

from event_agent.filters import curate_events
from event_agent.models import RawEvent

SGT = ZoneInfo("Asia/Singapore")
NOW = datetime(2026, 7, 13, 9, 0, tzinfo=SGT)  # Monday


def candidate(start_at: datetime, text: str, *, price: str = "Free") -> RawEvent:
    return RawEvent(
        source="Test",
        title="AI builders networking night",
        description=text,
        url=f"https://example.com/{start_at.timestamp()}",
        start_at=start_at,
        location="Singapore",
        price_text=price,
        raw_text=text,
    )


def test_weekday_must_be_strictly_after_6pm() -> None:
    at_six = candidate(datetime(2026, 7, 13, 18, 0, tzinfo=SGT), "Free admission")
    after_six = candidate(
        datetime(2026, 7, 13, 18, 1, tzinfo=SGT), "Free admission and networking"
    )
    events, report = curate_events(
        [at_six, after_six], keywords=("AI",), now=NOW, lookahead_days=90
    )
    assert [event.start_at.minute for event in events] == [1]
    assert report.rejected["time-window"] == 1


def test_weekend_accepts_morning_and_afternoon_only() -> None:
    saturday = datetime(2026, 7, 18, tzinfo=SGT)
    raw = [
        candidate(saturday.replace(hour=5, minute=59), "Free event"),
        candidate(saturday.replace(hour=6), "Free event"),
        candidate(saturday.replace(hour=17, minute=59), "Free event"),
        candidate(saturday.replace(hour=18), "Free event"),
    ]
    events, _report = curate_events(raw, keywords=("AI",), now=NOW, lookahead_days=90)
    assert [event.start_at.strftime("%H:%M") for event in events] == ["06:00", "17:59"]


def test_free_food_does_not_prove_free_admission() -> None:
    raw = candidate(
        datetime(2026, 7, 13, 19, 0, tzinfo=SGT),
        "Tickets from $25. Free food and beer provided.",
        price="$25",
    )
    events, report = curate_events([raw], keywords=("AI",), now=NOW, lookahead_days=90)
    assert events == []
    assert report.rejected["explicitly-paid"] == 1


def test_unstated_price_is_included_but_not_marked_free() -> None:
    raw = candidate(
        datetime(2026, 7, 13, 19, 0, tzinfo=SGT),
        "AI builders meetup with external registration",
        price="External registration",
    )
    events, report = curate_events([raw], keywords=("AI",), now=NOW, lookahead_days=90)
    assert len(events) == 1
    assert events[0].free_evidence == ""
    assert report.accepted == 1


def test_signup_metrics_are_propagated_to_curated_event() -> None:
    raw = candidate(
        datetime(2026, 7, 13, 19, 0, tzinfo=SGT),
        "Free AI builders meetup",
    )
    raw.metadata.update(
        attendee_count=120,
        capacity=150,
        seats_left=30,
        registration_status="open",
    )
    events, _report = curate_events([raw], keywords=("AI",), now=NOW, lookahead_days=90)
    assert events[0].attendee_count == 120
    assert events[0].capacity == 150
    assert events[0].seats_left == 30
    assert events[0].registration_status == "open"


def test_perks_raise_priority() -> None:
    plain = candidate(
        datetime(2026, 7, 14, 19, 0, tzinfo=SGT),
        "Free admission to an AI talk",
    )
    plain.url = "https://example.com/plain"
    perk = candidate(
        datetime(2026, 7, 15, 19, 0, tzinfo=SGT),
        "Free admission. Pizza, beer, refreshments and networking included.",
    )
    perk.url = "https://example.com/perk"
    events, _report = curate_events(
        [plain, perk], keywords=("AI", "Networking"), now=NOW, lookahead_days=90
    )
    assert events[0].url.endswith("/perk")
    assert events[0].perks == ("Pizza", "Beer", "Refreshments", "Networking")


def test_venue_name_does_not_count_as_a_provided_perk() -> None:
    raw = candidate(
        datetime(2026, 7, 14, 19, 0, tzinfo=SGT),
        "Free admission to an AI event\nSingapore Craft Beer Bar",
    )
    raw.title = "AI builders night"
    raw.location = "Singapore Craft Beer Bar"
    events, _report = curate_events([raw], keywords=("AI",), now=NOW, lookahead_days=90)
    assert events[0].perks == ()


def test_requires_singapore_location_and_keyword() -> None:
    no_location = candidate(
        datetime(2026, 7, 13, 19, 0, tzinfo=SGT), "Free AI event"
    )
    no_location.location = "Kuala Lumpur"
    no_location.description = "Free AI event in Kuala Lumpur"
    no_location.raw_text = no_location.description
    no_keyword = candidate(
        datetime(2026, 7, 14, 19, 0, tzinfo=SGT), "Free admission to a pottery class"
    )
    no_keyword.title = "Pottery class"
    events, report = curate_events(
        [no_location, no_keyword], keywords=("AI",), now=NOW, lookahead_days=90
    )
    assert events == []
    assert report.rejected == {"location": 1, "keyword": 1}
