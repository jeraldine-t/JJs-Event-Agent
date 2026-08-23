from event_agent.config import Settings


def test_blank_whatsapp_path_uses_safe_ignored_default(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("WHATSAPP_USER_DATA_DIR", "")
    monkeypatch.setenv("JJS_PRIVATE_STATE_DIR", str(tmp_path / "private"))
    monkeypatch.delenv("ENABLED_SOURCES", raising=False)
    settings = Settings.from_env(tmp_path)
    assert settings.whatsapp_user_data_dir == tmp_path / ".state/whatsapp"
    assert "whatsapp" not in settings.enabled_sources
    assert settings.enabled_sources == ("linkedin", "eventbrite", "luma", "meetup", "gdg")
    assert settings.meetup_max_events == 60
    assert settings.whatsapp_groups == ()
    assert settings.telegram_referral_urls_file == tmp_path / "private/telegram-referrals.json"
    assert settings.whatsapp_referral_urls_file == tmp_path / "private/whatsapp-referrals.json"
    assert settings.email_recipient == ""
