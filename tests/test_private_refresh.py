from pathlib import Path


def test_local_refresh_is_restricted_to_private_chat_sources() -> None:
    root = Path(__file__).resolve().parents[1]
    script = (root / "scripts" / "private-refresh.sh").read_text(encoding="utf-8")

    assert 'ENABLED_SOURCES="telegram,whatsapp"' in script
    assert 'ENABLED_SOURCES="eventbrite,luma,meetup,gdg,telegram,whatsapp"' not in script


def test_online_watcher_does_not_probe_or_scrape_public_sources() -> None:
    root = Path(__file__).resolve().parents[1]
    script = (root / "scripts" / "private-refresh-when-online.sh").read_text(encoding="utf-8")

    assert "luma.com" not in script
    assert "private-refresh.sh" in script
