from event_agent.config import Settings


def test_blank_whatsapp_path_uses_safe_ignored_default(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("WHATSAPP_USER_DATA_DIR", "")
    monkeypatch.delenv("ENABLED_SOURCES", raising=False)
    settings = Settings.from_env(tmp_path)
    assert settings.whatsapp_user_data_dir == tmp_path / ".state/whatsapp"
    assert "whatsapp" not in settings.enabled_sources
    assert settings.enabled_sources == ("linkedin", "eventbrite", "luma", "meetup")
